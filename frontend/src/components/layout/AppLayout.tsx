import Sidebar from "./Sidebar";
import Topbar from "./Topbar";

interface AppLayoutProps {
  title: string;
  children: React.ReactNode;
}

export default function AppLayout({ title, children }: AppLayoutProps) {
  return (
    <div className="flex min-h-screen bg-background">
      <Sidebar />
      <div className="flex-1 flex flex-col min-w-0">
        <Topbar title={title} />
        <main className="flex-1 p-6 max-w-[1440px]">{children}</main>
      </div>
    </div>
  );
}
