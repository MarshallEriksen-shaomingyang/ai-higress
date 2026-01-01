"use client";

import { oauthRedirect } from "@/lib/auth/oauth-redirect";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/lib/i18n-context";
import Image from "next/image";

interface OAuthButtonsProps {
  /**
   * 登录成功后的重定向地址（可选）
   * 如果不提供，将使用当前页面地址
   */
  redirectUrl?: string;

  /**
   * 是否显示分隔线
   */
  showDivider?: boolean;

  /**
   * 是否已同意服务条款
   */
  agreedToTerms?: boolean;

  /**
   * 当需要同意服务条款时的回调
   */
  onTermsRequired?: () => void;
}

export function OAuthButtons({
  redirectUrl,
  showDivider = true,
  agreedToTerms = false,
  onTermsRequired,
}: OAuthButtonsProps) {
  const { t } = useI18n();

  const handleLinuxDoLogin = () => {
    // 检查是否已同意服务条款
    if (!agreedToTerms) {
      onTermsRequired?.();
      return;
    }

    // 保存重定向地址
    if (redirectUrl) {
      oauthRedirect.save(redirectUrl);
    } else {
      oauthRedirect.save();
    }

    // 跳转到后端 LinuxDo OAuth 授权端点
    // 后端会生成 state 并重定向到 LinuxDo
    const apiBaseUrl = process.env.NEXT_PUBLIC_API_BASE_URL || "http://localhost:8000";
    window.location.href = `${apiBaseUrl}/auth/oauth/linuxdo/authorize`;
  };

  return (
    <div className="space-y-4">
      {showDivider && (
        <div className="relative">
          <div className="absolute inset-0 flex items-center">
            <span className="w-full border-t" />
          </div>
          <div className="relative flex justify-center text-xs uppercase">
            <span className="bg-background px-2 text-muted-foreground">
              {t("auth.oauth_divider")}
            </span>
          </div>
        </div>
      )}

      <div className="grid gap-3">
        {/* LinuxDo OAuth */}
        <Button
          type="button"
          variant="outline"
          onClick={handleLinuxDoLogin}
          className="w-full"
        >
          <Image
            src="/icon/linuxdo.svg"
            alt="LinuxDo"
            width={16}
            height={16}
            className="mr-2"
          />
          {t("auth.oauth_linuxdo")}
        </Button>
      </div>
    </div>
  );
}
