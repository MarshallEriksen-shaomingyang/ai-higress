import { AdaptiveSidebar } from "@/components/sidebars/adaptive-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TopNav } from "@/components/layout/top-nav";

export default function DashboardLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <SidebarProvider>
            <div className="flex h-screen bg-background overflow-hidden w-full">
                {/* 桌面端侧边栏 */}
                <AdaptiveSidebar />
                
                {/* 主内容区 */}
                <div className="flex-1 flex flex-col overflow-hidden">
                    <TopNav /><main className="flex-1 overflow-y-auto p-4 lg:p-6 glass-card">
                        {children}
                    </main>
                    
                </div>
            </div>
        </SidebarProvider>
    );
}
