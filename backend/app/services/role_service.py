from __future__ import annotations

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import Select, delete, select
from sqlalchemy.orm import Session

from app.models import Permission, Role, RolePermission, UserRole


class RoleServiceError(RuntimeError):
    """Base error for role management operations."""


class RoleCodeAlreadyExistsError(RoleServiceError):
    def __init__(self, code: str):
        super().__init__(f"Role code '{code}' already exists")
        self.code = code


class UnknownPermissionCodeError(RoleServiceError):
    def __init__(self, missing_codes: set[str]):
        self.missing_codes = missing_codes
        message = "Unknown permission codes: " + ", ".join(sorted(missing_codes))
        super().__init__(message)


class UnknownRoleIdError(RoleServiceError):
    def __init__(self, missing_ids: set[UUID]):
        self.missing_ids = missing_ids
        message = "Unknown role ids: " + ", ".join(str(i) for i in sorted(missing_ids, key=str))
        super().__init__(message)


class RoleService:
    """角色与角色权限/用户角色管理逻辑。"""

    def __init__(self, session: Session):
        self.session = session

    # ---- 角色定义 ----

    def list_roles(self) -> list[Role]:
        stmt: Select[tuple[Role]] = select(Role).order_by(Role.code)
        return list(self.session.execute(stmt).scalars().all())

    def get_role(self, role_id: UUID) -> Role | None:
        return self.session.get(Role, role_id)

    def get_role_by_code(self, code: str) -> Role | None:
        stmt: Select[tuple[Role]] = select(Role).where(Role.code == code)
        return self.session.execute(stmt).scalars().first()

    def create_role(self, code: str, name: str, description: str | None = None) -> Role:
        normalized_code = (code or "").strip()
        if not normalized_code:
            raise ValueError("role code must not be empty")

        if self.get_role_by_code(normalized_code) is not None:
            raise RoleCodeAlreadyExistsError(normalized_code)

        role = Role(code=normalized_code, name=name, description=description)
        self.session.add(role)
        self.session.commit()
        self.session.refresh(role)
        return role

    def update_role(
        self,
        role: Role,
        *,
        name: str | None = None,
        description: str | None = None,
    ) -> Role:
        updated = False
        if name is not None:
            role.name = name
            updated = True
        if description is not None:
            role.description = description
            updated = True
        if updated:
            self.session.add(role)
            self.session.commit()
            self.session.refresh(role)
        return role

    def delete_role(self, role: Role) -> None:
        """删除角色，级联删除角色权限与用户角色。"""

        self.session.delete(role)
        self.session.commit()

    # ---- 角色权限 ----

    def get_role_permission_codes(self, role: Role) -> list[str]:
        """返回指定角色当前拥有的权限 code 列表（已去重、排序）。"""

        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        )
        codes = self.session.execute(stmt).scalars().all()
        return sorted(set(codes))

    def set_role_permissions(
        self,
        role: Role,
        permission_codes: Sequence[str],
    ) -> list[str]:
        """将角色的权限设置为给定的 permission_codes 集合。

        会清理多余的 RolePermission，并新增缺失的绑定。
        """

        normalized_codes: set[str] = set()
        for code in permission_codes:
            trimmed = (code or "").strip()
            if trimmed:
                normalized_codes.add(trimmed)

        if not normalized_codes:
            # 没有任何权限 => 清空
            stmt = delete(RolePermission).where(RolePermission.role_id == role.id)
            self.session.execute(stmt)
            self.session.commit()
            self.session.expire(role, ["role_permissions"])
            return []

        # 检查所有权限 code 是否存在
        permissions_stmt: Select[tuple[Permission]] = select(Permission).where(
            Permission.code.in_(normalized_codes)
        )
        permissions = list(self.session.execute(permissions_stmt).scalars().all())
        found_codes = {p.code for p in permissions}
        missing = normalized_codes - found_codes
        if missing:
            raise UnknownPermissionCodeError(missing)

        # 当前已有的绑定
        current_stmt: Select[tuple[RolePermission]] = select(RolePermission).where(
            RolePermission.role_id == role.id
        )
        current_links = list(self.session.execute(current_stmt).scalars().all())
        current_by_code = {link.permission.code: link for link in current_links}

        desired_codes = found_codes
        to_remove = set(current_by_code.keys()) - desired_codes
        to_add = desired_codes - set(current_by_code.keys())

        # 删除不再需要的绑定
        if to_remove:
            ids_to_remove = [
                link.permission_id
                for code, link in current_by_code.items()
                if code in to_remove
            ]
            if ids_to_remove:
                stmt = delete(RolePermission).where(
                    RolePermission.role_id == role.id,
                    RolePermission.permission_id.in_(ids_to_remove),
                )
                self.session.execute(stmt)

        # 新增缺失的绑定
        code_to_permission = {p.code: p for p in permissions}
        for code in to_add:
            perm = code_to_permission[code]
            self.session.add(
                RolePermission(role_id=role.id, permission_id=perm.id)
            )

        self.session.commit()
        self.session.expire(role, ["role_permissions"])
        return sorted(desired_codes)

    # ---- 用户角色 ----

    def get_user_roles(self, user_id: UUID) -> list[Role]:
        stmt = (
            select(Role)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
            .order_by(Role.code)
        )
        return list(self.session.execute(stmt).scalars().all())

    def set_user_roles(self, user_id: UUID, role_ids: Sequence[UUID]) -> list[Role]:
        """将用户的角色设置为给定 role_ids 集合。"""

        normalized_ids: set[UUID] = {rid for rid in role_ids if rid}

        if not normalized_ids:
            stmt = delete(UserRole).where(UserRole.user_id == user_id)
            self.session.execute(stmt)
            self.session.commit()
            return []

        # 检查 role 是否存在
        roles_stmt: Select[tuple[Role]] = select(Role).where(Role.id.in_(normalized_ids))
        roles = list(self.session.execute(roles_stmt).scalars().all())
        found_ids = {r.id for r in roles}
        missing_ids = normalized_ids - found_ids
        if missing_ids:
            raise UnknownRoleIdError(missing_ids)

        # 当前已有的用户角色
        current_stmt: Select[tuple[UserRole]] = select(UserRole).where(
            UserRole.user_id == user_id
        )
        current_links = list(self.session.execute(current_stmt).scalars().all())
        current_role_ids = {link.role_id for link in current_links}

        desired_ids = found_ids
        to_remove = current_role_ids - desired_ids
        to_add = desired_ids - current_role_ids

        if to_remove:
            stmt = delete(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id.in_(to_remove),
            )
            self.session.execute(stmt)

        for rid in to_add:
            self.session.add(UserRole(user_id=user_id, role_id=rid))

        self.session.commit()
        return sorted(roles, key=lambda r: r.code)


__all__ = [
    "RoleCodeAlreadyExistsError",
    "RoleService",
    "RoleServiceError",
    "UnknownPermissionCodeError",
    "UnknownRoleIdError",
]
