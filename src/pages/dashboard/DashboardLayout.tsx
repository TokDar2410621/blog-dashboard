import { Routes, Route } from "react-router-dom";
import { SidebarProvider, SidebarInset } from "@/components/ui/sidebar";
import { DashboardSidebar } from "@/components/DashboardSidebar";
import Overview from "./Overview";
import PostList from "./PostList";
import PostEditor from "./PostEditor";
import AIGenerator from "./AIGenerator";
import ImageGallery from "./ImageGallery";

export default function DashboardLayout() {
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full">
        <DashboardSidebar />
        <SidebarInset className="flex-1">
          <div className="p-6">
            <Routes>
              <Route index element={<Overview />} />
              <Route path="articles" element={<PostList />} />
              <Route path="articles/nouveau" element={<PostEditor />} />
              <Route path="articles/:slug" element={<PostEditor />} />
              <Route path="generer" element={<AIGenerator />} />
              <Route path="images" element={<ImageGallery />} />
            </Routes>
          </div>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
