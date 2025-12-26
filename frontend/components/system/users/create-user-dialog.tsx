"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
    Dialog,
    DialogContent,
    DialogDescription,
    DialogFooter,
    DialogHeader,
    DialogTitle,
} from "@/components/ui/dialog";
import { useI18n } from "@/lib/i18n-context";
import { toast } from "sonner";
import { useCreateUser } from "@/lib/swr/use-users";

interface CreateUserDialogProps {
    open: boolean;
    onOpenChange: (open: boolean) => void;
    onSuccess: () => void;
}

export function CreateUserDialog({ open, onOpenChange, onSuccess }: CreateUserDialogProps) {
    const { t } = useI18n();
    const createUser = useCreateUser();
    const [formData, setFormData] = useState({
        email: "",
        password: "",
        display_name: ""
    });

    const handleCreate = async () => {
        try {
            await createUser(formData);
            toast.success("User created successfully");
            onOpenChange(false);
            onSuccess();
            setFormData({ email: "", password: "", display_name: "" });
        } catch (error) {
            toast.error("Failed to create user");
        }
    };

    return (
        <Dialog open={open} onOpenChange={onOpenChange}>
            <DialogContent>
                <DialogHeader>
                    <DialogTitle>{t("users.add_user")}</DialogTitle>
                    <DialogDescription>Create a new user account</DialogDescription>
                </DialogHeader>
                <div className="space-y-4 py-4">
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Email</label>
                        <Input
                            type="email"
                            value={formData.email}
                            onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                            placeholder="john@example.com"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Display Name</label>
                        <Input
                            value={formData.display_name}
                            onChange={(e) => setFormData({ ...formData, display_name: e.target.value })}
                            placeholder="John Doe"
                        />
                    </div>
                    <div className="space-y-2">
                        <label className="text-sm font-medium">Password</label>
                        <Input
                            type="password"
                            value={formData.password}
                            onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                            placeholder="••••••••"
                        />
                    </div>
                </div>
                <DialogFooter>
                    <Button variant="outline" onClick={() => onOpenChange(false)}>
                        {t("providers.btn_cancel")}
                    </Button>
                    <Button onClick={handleCreate}>{t("providers.btn_create")}</Button>
                </DialogFooter>
            </DialogContent>
        </Dialog>
    );
}
