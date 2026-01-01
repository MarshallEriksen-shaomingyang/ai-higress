"use client";

import { useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import Link from "next/link";
import { BrushBorder } from "@/components/ink/brush-border";
import { InkButton } from "@/components/ink/ink-button";
import { FormInput } from "@/components/forms/form-input";
import { useI18n } from "@/lib/i18n-context";
import { useAuthStore } from "@/lib/stores/auth-store";
import { OAuthButtons } from "@/components/auth/oauth-buttons";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";

type AuthMode = "login" | "register";

// 登录表单验证
const loginSchema = z.object({
  email: z.string().email("请输入有效的邮箱地址"),
  password: z.string().min(6, "密码至少6个字符").max(128, "密码最多128个字符"),
  rememberMe: z.boolean().optional(),
});

// 注册表单验证
const registerSchema = z.object({
  email: z.string().email("请输入有效的邮箱地址"),
  password: z.string().min(6, "密码至少6个字符").max(128, "密码最多128个字符"),
  confirmPassword: z.string(),
}).refine((data) => data.password === data.confirmPassword, {
  message: "两次输入的密码不一致",
  path: ["confirmPassword"],
});

type LoginFormData = z.infer<typeof loginSchema>;
type RegisterFormData = z.infer<typeof registerSchema>;

export function AuthDialog() {
  const { t } = useI18n();
  const router = useRouter();
  const searchParams = useSearchParams();
  const [mode, setMode] = useState<AuthMode>("login");
  const [agreedToTerms, setAgreedToTerms] = useState(false);
  const [showTermsError, setShowTermsError] = useState(false);
  const {
    login,
    register: registerUser,
    isLoading,
    isAuthDialogOpen,
    closeAuthDialog
  } = useAuthStore();

  const isLogin = mode === "login";
  const redirectTo = searchParams.get('redirect') || '/dashboard/overview';

  // 登录表单
  const loginForm = useForm<LoginFormData>({
    resolver: zodResolver(loginSchema),
    defaultValues: {
      email: "",
      password: "",
      rememberMe: true,
    },
  });

  // 注册表单
  const registerForm = useForm<RegisterFormData>({
    resolver: zodResolver(registerSchema),
    defaultValues: {
      email: "",
      password: "",
      confirmPassword: "",
    },
  });

  // 处理登录
  const handleLogin = async (data: LoginFormData) => {
    if (!agreedToTerms) {
      setShowTermsError(true);
      return;
    }
    setShowTermsError(false);
    try {
      const { rememberMe, ...loginData } = data;
      await login(loginData, { remember: rememberMe ?? true });
      // 登录成功后，对话框会自动关闭（在 auth-store 中处理）
      // 如果有重定向参数，则跳转；否则刷新当前页面
      if (searchParams.get('redirect')) {
        router.push(redirectTo);
      } else {
        // 使用 router.refresh() 刷新服务端组件，然后重新导航到当前页面以确保客户端组件也更新
        router.refresh();
      }
    } catch (error) {
      console.error('Login error:', error);
      // 不做额外处理，错误已经在 auth-store 中通过 toast 显示
    }
  };

  // 处理注册
  const handleRegister = async (data: RegisterFormData) => {
    if (!agreedToTerms) {
      setShowTermsError(true);
      return;
    }
    setShowTermsError(false);
    try {
      const { confirmPassword, ...registerData } = data;
      await registerUser(registerData);
      // 注册成功后会自动登录，对话框会自动关闭
      if (searchParams.get('redirect')) {
        router.push(redirectTo);
      } else {
        // 使用 router.refresh() 刷新服务端组件，然后重新导航到当前页面以确保客户端组件也更新
        router.refresh();
      }
    } catch (error) {
      console.error('Register error:', error);
      // 不做额外处理，错误已经在 auth-store 中通过 toast 显示
    }
  };

  // 协议勾选变更处理
  const handleTermsChange = (checked: boolean) => {
    setAgreedToTerms(checked);
    if (checked) {
      setShowTermsError(false);
    }
  };

  // 协议勾选组件
  const TermsAgreement = () => (
    <div className="space-y-1">
      <label className="flex items-start space-x-2 cursor-pointer text-sm">
        <input
          type="checkbox"
          checked={agreedToTerms}
          onChange={(e) => handleTermsChange(e.target.checked)}
          className="mt-0.5 rounded border-gray-300"
        />
        <span className="text-muted-foreground leading-relaxed">
          {t("legal.agree_prefix")}
          <Link
            href="/legal/terms"
            target="_blank"
            className="text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {t("legal.terms_of_service")}
          </Link>
          {t("legal.and")}
          <Link
            href="/legal/privacy"
            target="_blank"
            className="text-primary hover:underline"
            onClick={(e) => e.stopPropagation()}
          >
            {t("legal.privacy_policy")}
          </Link>
        </span>
      </label>
      {showTermsError && (
        <p className="text-destructive text-xs pl-6">
          {t("legal.agreement_required")}
        </p>
      )}
    </div>
  );

  return (
    <Dialog open={isAuthDialogOpen} onOpenChange={closeAuthDialog}>
      <DialogContent className="max-w-md w-full">
        <DialogHeader className="text-center">
          <DialogTitle className="text-2xl font-serif font-bold">
            {t("app.title")}
          </DialogTitle>
          <DialogDescription>
            {isLogin ? t("auth.login.subtitle") : t("auth.register.subtitle")}
          </DialogDescription>
        </DialogHeader>

        {/* OAuth 登录按钮 */}
        <OAuthButtons
          redirectUrl={redirectTo}
          agreedToTerms={agreedToTerms}
          onTermsRequired={() => setShowTermsError(true)}
        />

        <BrushBorder className="mt-4">
          {isLogin ? (
            <form onSubmit={loginForm.handleSubmit(handleLogin)} className="space-y-6">
              <FormInput
                label={t("auth.email_label")}
                type="email"
                placeholder={t("auth.email_placeholder")}
                {...loginForm.register("email")}
                error={loginForm.formState.errors.email?.message}
              />

              <FormInput
                label={t("auth.password_label")}
                type="password"
                placeholder={t("auth.password_placeholder")}
                {...loginForm.register("password")}
                error={loginForm.formState.errors.password?.message}
              />

              <div className="flex items-center justify-between text-sm">
                <label className="flex items-center space-x-2 cursor-pointer">
                  <input
                    type="checkbox"
                    className="rounded border-gray-300"
                    {...loginForm.register("rememberMe")}
                  />
                  <span>{t("auth.remember_me")}</span>
                </label>
                <Link href="#" className="text-primary hover:underline">
                  {t("auth.forgot_password")}
                </Link>
              </div>

              <TermsAgreement />

              <InkButton
                className="w-full"
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? "登录中..." : t("auth.login_button")}
              </InkButton>
            </form>
          ) : (
            <form onSubmit={registerForm.handleSubmit(handleRegister)} className="space-y-6">
              <FormInput
                label={t("auth.email_label")}
                type="email"
                placeholder={t("auth.email_placeholder")}
                {...registerForm.register("email")}
                error={registerForm.formState.errors.email?.message}
              />

              <FormInput
                label={t("auth.password_label")}
                type="password"
                placeholder={t("auth.password_placeholder")}
                {...registerForm.register("password")}
                error={registerForm.formState.errors.password?.message}
              />

              <FormInput
                label={t("auth.confirm_password_label")}
                type="password"
                placeholder={t("auth.confirm_password_placeholder")}
                {...registerForm.register("confirmPassword")}
                error={registerForm.formState.errors.confirmPassword?.message}
              />

              <TermsAgreement />

              <InkButton
                className="w-full"
                type="submit"
                disabled={isLoading}
              >
                {isLoading ? "注册中..." : t("auth.register_button")}
              </InkButton>
            </form>
          )}
        </BrushBorder>

        <div className="mt-4 text-center text-sm">
          {isLogin ? (
            <p className="text-muted-foreground">
              {t("auth.no_account")}{" "}
              <button
                type="button"
                onClick={() => setMode("register")}
                className="text-primary hover:underline font-medium"
              >
                {t("auth.signup_link")}
              </button>
            </p>
          ) : (
            <p className="text-muted-foreground">
              {t("auth.have_account")}{" "}
              <button
                type="button"
                onClick={() => setMode("login")}
                className="text-primary hover:underline font-medium"
              >
                {t("auth.signin_link")}
              </button>
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
