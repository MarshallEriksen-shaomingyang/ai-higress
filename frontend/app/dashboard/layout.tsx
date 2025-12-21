import { AdaptiveSidebar } from "@/components/sidebars/adaptive-sidebar";
import { TopNav } from "@/components/layout/top-nav";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <div className="flex h-screen bg-background overflow-hidden w-full">
            {/* 桌面端侧边栏 */}
            <AdaptiveSidebar />
            
            {/* 主内容区 */}
                <div className="flex-1 flex flex-col overflow-hidden min-h-0">
                    <TopNav />
                <main className="flex-1 overflow-y-auto no-scrollbar min-h-0 p-4 lg:p-6 glass-card">
                    {children}
                </main>
            </div>
        </div>
    );
}
