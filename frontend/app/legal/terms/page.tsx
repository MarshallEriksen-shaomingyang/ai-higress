"use client";

import { useI18n } from "@/lib/i18n-context";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";

export default function TermsOfServicePage() {
  const { t } = useI18n();

  return (
    <div className="min-h-screen bg-background">
      <div className="container max-w-4xl mx-auto px-4 py-8">
        <Link
          href="/"
          className="inline-flex items-center text-muted-foreground hover:text-foreground mb-8"
        >
          <ArrowLeft className="mr-2 h-4 w-4" />
          返回首页
        </Link>

        <article className="prose prose-neutral dark:prose-invert max-w-none">
          <h1 className="text-3xl font-bold mb-2">{t("legal.terms.title")}</h1>
          <p className="text-muted-foreground mb-8">{t("legal.terms.effective_date")}</p>

          <p className="lead">{t("legal.terms.welcome")}</p>

          {/* Section 1: Service Description */}
          <h2>{t("legal.terms.section1.title")}</h2>
          <p>{t("legal.terms.section1.content")}</p>

          {/* Section 2: User Eligibility */}
          <h2>{t("legal.terms.section2.title")}</h2>
          <p>{t("legal.terms.section2.content")}</p>

          {/* Section 3: Acceptable Use Policy */}
          <h2>{t("legal.terms.section3.title")}</h2>
          <p>{t("legal.terms.section3.intro")}</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>{t("legal.terms.section3.item1")}</li>
            <li>{t("legal.terms.section3.item2")}</li>
            <li>{t("legal.terms.section3.item3")}</li>
            <li>{t("legal.terms.section3.item4")}</li>
            <li>{t("legal.terms.section3.item5")}</li>
            <li>{t("legal.terms.section3.item6")}</li>
            <li>{t("legal.terms.section3.item7")}</li>
            <li>{t("legal.terms.section3.item8")}</li>
            <li>{t("legal.terms.section3.item9")}</li>
            <li>{t("legal.terms.section3.item10")}</li>
          </ul>

          {/* Section 4: User Responsibilities */}
          <h2>{t("legal.terms.section4.title")}</h2>
          <p>{t("legal.terms.section4.content")}</p>

          {/* Section 5: Intellectual Property */}
          <h2>{t("legal.terms.section5.title")}</h2>
          <p>{t("legal.terms.section5.content")}</p>

          {/* Section 6: Disclaimer of Warranties */}
          <h2>{t("legal.terms.section6.title")}</h2>
          <p className="font-medium">{t("legal.terms.section6.intro")}</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>{t("legal.terms.section6.item1")}</li>
            <li>{t("legal.terms.section6.item2")}</li>
            <li>{t("legal.terms.section6.item3")}</li>
            <li>{t("legal.terms.section6.item4")}</li>
            <li>{t("legal.terms.section6.item5")}</li>
          </ul>

          {/* Section 7: AI Content Disclaimer */}
          <h2>{t("legal.terms.section7.title")}</h2>
          <p>{t("legal.terms.section7.intro")}</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>{t("legal.terms.section7.item1")}</li>
            <li>{t("legal.terms.section7.item2")}</li>
            <li>{t("legal.terms.section7.item3")}</li>
            <li>{t("legal.terms.section7.item4")}</li>
            <li>{t("legal.terms.section7.item5")}</li>
          </ul>

          {/* Section 8: Third-Party Services Disclaimer */}
          <h2>{t("legal.terms.section8.title")}</h2>
          <p>{t("legal.terms.section8.content")}</p>

          {/* Section 9: Limitation of Liability */}
          <h2>{t("legal.terms.section9.title")}</h2>
          <p className="font-medium">{t("legal.terms.section9.intro")}</p>
          <ul className="list-disc pl-6 space-y-2">
            <li>{t("legal.terms.section9.item1")}</li>
            <li>{t("legal.terms.section9.item2")}</li>
            <li>{t("legal.terms.section9.item3")}</li>
            <li>{t("legal.terms.section9.item4")}</li>
          </ul>

          {/* Section 10: Indemnification */}
          <h2>{t("legal.terms.section10.title")}</h2>
          <p>{t("legal.terms.section10.content")}</p>

          {/* Section 11: Termination */}
          <h2>{t("legal.terms.section11.title")}</h2>
          <p>{t("legal.terms.section11.content")}</p>

          {/* Section 12: Governing Law */}
          <h2>{t("legal.terms.section12.title")}</h2>
          <p>{t("legal.terms.section12.content")}</p>

          {/* Section 13: Changes to Terms */}
          <h2>{t("legal.terms.section13.title")}</h2>
          <p>{t("legal.terms.section13.content")}</p>

          <hr className="my-8" />
          <p className="text-muted-foreground">{t("legal.terms.contact")}</p>
        </article>
      </div>
    </div>
  );
}
