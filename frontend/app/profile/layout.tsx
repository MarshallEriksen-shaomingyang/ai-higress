import { AdaptiveSidebar } from "@/components/sidebars/adaptive-sidebar";
import { SidebarProvider } from "@/components/ui/sidebar";
import { TopNav } from "@/components/layout/top-nav";

export default function ProfileLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    return (
        <SidebarProvider>
            <div className="flex h-screen bg-background overflow-hidden w-full">
                <AdaptiveSidebar />
                <div className="flex-1 flex flex-col overflow-hidden">
                    <TopNav />
                    <main className="flex-1 overflow-y-auto no-scrollbar">
                        {children}
                    </main>
                </div>
            </div>
        </SidebarProvider>
    );
}
