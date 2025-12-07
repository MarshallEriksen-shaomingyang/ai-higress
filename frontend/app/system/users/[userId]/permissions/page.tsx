import { adminService } from "@/http/admin";
import { PermissionsPageClient } from "./components/permissions-page-client";
import { notFound } from "next/navigation";

interface PageProps {
  params: Promise<{
    userId: string;
  }>;
}

export default async function UserPermissionsPage({ params }: PageProps) {
  // Next.js 15 中 params 是 Promise，这里先解包
  const { userId } = await params;

  let user = null;

  try {
    // Fetch user data on the server
    const users = await adminService.getAllUsers();
    user = users.find((u) => u.id === userId) || null;
  } catch (error) {
    console.error("Failed to fetch user:", error);
    notFound();
  }

  if (!user) {
    notFound();
  }

  return <PermissionsPageClient user={user} userId={userId} />;
}
