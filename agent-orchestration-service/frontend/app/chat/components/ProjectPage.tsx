import React, { useState, useEffect } from 'react';
import { observer } from 'mobx-react-lite';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Input } from '@/components/ui/input';
import { SidebarTrigger } from '@/components/ui/sidebar';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { MoreHorizontal, Trash2, SquarePen, X, Check, FolderOpen, Plus, Sparkles, FileText } from 'lucide-react';
import { projectStore } from '@/app/stores/projectStore';
import { selectionStore } from '@/app/stores/selectionStore';
import LoadingSpinner from '@/components/layout/LoadingSpinner';
import { ProjectWithRuns } from '@/lib/types';

interface ProjectPageProps {
  currentInput: string;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
  onKeyPress: (e: React.KeyboardEvent) => void;
  isLoading: boolean;
}

export const ProjectPage = observer(function ProjectPage({
  currentInput,
  onInputChange,
  onSendMessage,
  onKeyPress,
  isLoading,
}: ProjectPageProps) {
  // Get data directly from the store, call methods via projectStore.methodName()
  const { projects, loading } = projectStore;
  
  // Get current project info from the selected project
  const currentProject = projects.find((p: ProjectWithRuns) => 
    p.project.project_id === selectionStore.selectedProject?.projectId
  );
  
  const [isEditingName, setIsEditingName] = useState(false);
  const [editingProjectName, setEditingProjectName] = useState('');
  // const [instructions, setInstructions] = useState('');
  // const [isEditingInstructions, setIsEditingInstructions] = useState(false);
  // const [editingInstructions, setEditingInstructions] = useState('');
  const [isDeleteDialogOpen, setIsDeleteDialogOpen] = useState(false);
  const [isUpdating, setIsUpdating] = useState(false);

  // Check if it's the default project
  const isDefaultProject = currentProject?.project.project_id === 'default';
  
  // Current project name - fully based on selectionStore to ensure real-time sync
  const projectName = selectionStore.selectedProject?.projectName || 'Unknown Project';

  // When the project changes, update local state
  useEffect(() => {
    if (currentProject && selectionStore.selectedProject) {
      // Ensure selectionStore has the latest project information
      if (selectionStore.selectedProject.projectId === currentProject.project.project_id) {
        // If the project name in selectionStore differs from the database, prefer the name from selectionStore (the latest value during an update)
        const nameToUse = selectionStore.selectedProject.projectName;
        setEditingProjectName(nameToUse);
        
        // Debug info
        console.log('ProjectPage sync:', {
          storeProjectName: selectionStore.selectedProject.projectName,
          dbProjectName: currentProject.project.name,
          usingName: nameToUse
        });
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentProject, selectionStore.selectedProject]);

  // Handle project name update
  const handleUpdateProjectName = async () => {
    if (!currentProject || !editingProjectName.trim() || isDefaultProject) return;
    
    try {
      setIsUpdating(true);
      
      console.log('ProjectPage updating:', editingProjectName.trim());
      
              // Only call the API; subsequent sync relies entirely on projectStore.updateProject() → loadProjects() → updateProjectsMap()
              await projectStore.updateProject(currentProject.project.project_id, { 
          name: editingProjectName.trim() 
        });
      
      setIsEditingName(false);
    } catch (error) {
      console.error('Failed to update project name:', error);
      // A toast notification for the error can be added here
    } finally {
      setIsUpdating(false);
    }
  };

  // Handle project deletion
  const handleDeleteProject = async () => {
    if (!currentProject || isDefaultProject) return;
    
    try {
      setIsUpdating(true);
      await projectStore.deleteProject(currentProject.project.project_id);
      
      // Clear selection state after successful deletion
      selectionStore.clearSelection();
      
      // Trigger a global project list refresh to ensure AppSidebar updates immediately
      selectionStore.triggerProjectsRefresh();
      
      // Close the delete confirmation dialog
      setIsDeleteDialogOpen(false);
      
      // Optional: navigate back to home page or other pages
      // router.push('/');
    } catch (error) {
      console.error('Failed to delete project:', error);
      // A toast notification for the error can be added here
    } finally {
      setIsUpdating(false);
    }
  };

  // Cancel editing project name - use the currently displayed name, not the old one from the database
  const handleCancelEditName = () => {
    setEditingProjectName(projectName);
    setIsEditingName(false);
  };

  // Start editing project name
  const handleStartEditName = () => {
    if (isDefaultProject) return;
    setEditingProjectName(projectName);
    setIsEditingName(true);
  };

  // If project data is loading, show loading state.
  // But if there is already project data, it means an update is in progress, so don't show full-screen loading.
  if (loading && projects.length === 0) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-shrink-0 h-12 bg-white flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <LoadingSpinner />
        </div>
      </div>
    );
  }

  // If data loading is complete but the project is not found, show an error state
  if (!currentProject) {
    return (
      <div className="flex flex-col h-screen">
        <div className="flex-shrink-0 h-12 bg-white flex items-center justify-between px-3">
          <div className="flex items-center gap-2">
            <SidebarTrigger />
          </div>
        </div>
        <div className="flex-1 flex items-center justify-center">
          <div className="text-center text-gray-500">
            <p>项目未找到</p>
            <Button 
              variant="outline" 
              onClick={() => selectionStore.clearSelection()}
              className="mt-4"
            >
              返回首页
            </Button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-50">
      <div className="flex-shrink-0 h-16 bg-white/80 backdrop-blur-sm border-b border-gray-100 flex items-center justify-between px-6">
        <div className="flex items-center gap-3">
          <SidebarTrigger />
          <div className="flex items-center gap-2">
            <FolderOpen className="w-5 h-5 text-blue-600" />
            <span className="font-semibold text-gray-800">项目详情</span>
          </div>
        </div>
      </div>
      <div className="flex-1 flex items-center justify-center px-6 py-8">
        <div className="w-full max-w-4xl bg-white/80 backdrop-blur-sm rounded-2xl shadow-xl border border-gray-200/50 p-8">
          {/* Header */}
          <header className="flex justify-between items-start mb-8">
            <div className="flex items-center gap-3">
              {isEditingName ? (
                <div className="flex items-center gap-3">
                  <Input
                    value={editingProjectName}
                    onChange={(e) => setEditingProjectName(e.target.value)}
                    className="text-2xl font-bold h-auto border-2 border-blue-200 focus:border-blue-500 rounded-lg"
                    autoFocus
                    disabled={isUpdating}
                    onKeyPress={(e) => {
                      if (e.key === 'Enter') {
                        handleUpdateProjectName();
                      } else if (e.key === 'Escape') {
                        handleCancelEditName();
                      }
                    }}
                  />
                  <Button 
                    variant="outline" 
                    className="h-10 w-10" 
                    size="icon" 
                    onClick={handleCancelEditName}
                    disabled={isUpdating}
                  >
                    <X className="h-4 w-4" />
                  </Button>
                  <Button 
                    className="h-10 w-10 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700" 
                    size="icon" 
                    onClick={handleUpdateProjectName}
                    disabled={isUpdating || !editingProjectName.trim()}
                  >
                    <Check className="h-4 w-4" />
                  </Button>
                </div>
              ) : (
                <div className="group relative flex items-center gap-4">
                  <div className="bg-gradient-to-r from-blue-500 to-indigo-600 p-3 rounded-xl shadow-lg">
                    <FolderOpen className="w-6 h-6 text-white" />
                  </div>
                  <div>
                    <h1
                      className={`text-3xl font-bold bg-gradient-to-r from-gray-800 to-gray-600 bg-clip-text text-transparent ${
                        isDefaultProject ? 'cursor-default' : 'cursor-pointer hover:from-blue-600 hover:to-indigo-600'
                      }`}
                      onClick={handleStartEditName}
                    >
                      {projectName}
                    </h1>
                    <p className="text-gray-500 mt-1">管理您的项目和代码生成</p>
                  </div>
                  {!isDefaultProject && (
                    <Button
                      variant="ghost"
                      size="icon"
                      className="h-10 w-10 opacity-0 group-hover:opacity-100 transition-all duration-200 hover:bg-blue-100"
                      onClick={handleStartEditName}
                    >
                      <SquarePen className="h-4 w-4 text-blue-600" />
                    </Button>
                  )}
                </div>
              )}
            </div>
            
            {/* Only show the actions menu for non-default projects */}
            {!isDefaultProject && (
              <DropdownMenu>
                <DropdownMenuTrigger asChild>
                  <Button variant="outline" size="icon" disabled={isUpdating} className="h-10 w-10 border-gray-200 hover:bg-gray-50">
                    <MoreHorizontal className="h-5 w-5" />
                  </Button>
                </DropdownMenuTrigger>
                <DropdownMenuContent align="end" className="w-48">
                  <DropdownMenuItem 
                    className="text-red-600 focus:text-red-600 focus:bg-red-50 flex items-center gap-3"
                    onClick={() => {
                      // Use setTimeout to ensure DropdownMenu is fully closed before opening the Dialog
                      setTimeout(() => {
                        setIsDeleteDialogOpen(true);
                      }, 0);
                    }}
                  >
                    <Trash2 className="h-4 w-4" />
                    <span>删除项目</span>
                  </DropdownMenuItem>
                </DropdownMenuContent>
              </DropdownMenu>
            )}
          </header>

          <main className="flex-1 space-y-8">
            {/* Chat Input Section */}
            <div className="bg-gradient-to-r from-blue-50 to-indigo-50 rounded-xl p-6 border border-blue-100">
              <div className="flex items-center gap-3 mb-4">
                <div className="bg-blue-100 p-2 rounded-lg">
                  <Sparkles className="w-5 h-5 text-blue-600" />
                </div>
                <h2 className="text-xl font-bold text-gray-800">开始您的AI助手体验</h2>
              </div>
              <p className="text-gray-600 mb-6">描述您的项目需求，或提出技术问题，我将为您提供专业的解决方案。</p>
              <div className="relative">
                <Textarea
                  value={currentInput}
                  onChange={(e) => onInputChange(e.target.value)}
                  onKeyPress={onKeyPress}
                  placeholder="例如：帮我创建一个React项目、优化这段代码、解释这个错误..."
                  className="min-h-[120px] resize-none w-full rounded-xl border-0 bg-white/80 backdrop-blur-sm p-4 pr-28 shadow-sm focus-visible:ring-2 focus-visible:ring-blue-500 focus-visible:ring-offset-0"
                />
                <Button
                  onClick={onSendMessage}
                  disabled={!currentInput.trim() || isLoading}
                  className="absolute right-3 bottom-3 bg-gradient-to-r from-blue-500 to-indigo-600 hover:from-blue-600 hover:to-indigo-700 px-6 py-2 rounded-lg shadow-lg transition-all duration-200"
                >
                  {isLoading ? (
                    <div className="flex items-center gap-2">
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      处理中...
                    </div>
                  ) : (
                    "开始对话"
                  )}
                </Button>
              </div>
            </div>

            {/* Project Instructions Section */}
            {/* <div>
              <div className="group relative flex items-center gap-3 mb-3">
                <h2 className="text-lg font-semibold">Project Instructions</h2>
                <Button
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8 opacity-0 group-hover:opacity-100 transition-opacity"
                  onClick={() => {
                    setEditingInstructions(instructions);
                    setIsEditingInstructions(true);
                  }}
                >
                  <SquarePen className="h-4 w-4" />
                </Button>
              </div>
              {isEditingInstructions ? (
                <div className="space-y-3">
                  <Textarea
                    value={editingInstructions}
                    onChange={(e) => setEditingInstructions(e.target.value)}
                    placeholder="Provide instructions for the agent. Be clear and concise."
                    className="min-h-[120px] w-full rounded-lg border p-4"
                    autoFocus
                  />
                  <div className="flex justify-end gap-2">
                    <Button variant="ghost" onClick={() => setIsEditingInstructions(false)}>Cancel</Button>
                    <Button onClick={() => {
                      setInstructions(editingInstructions);
                      setIsEditingInstructions(false);
                    }}>Save</Button>
                  </div>
                </div>
              ) : (
                <div
                  className="text-gray-500 min-h-[40px] cursor-text"
                  onClick={() => {
                    setEditingInstructions(instructions);
                    setIsEditingInstructions(true);
                  }}
                >
                  {instructions || 'Click to add project instructions.'}
                </div>
              )}
            </div> */}

            {/* Project Files Section */}
            <div className="bg-white/60 backdrop-blur-sm rounded-xl p-6 border border-gray-200/50">
              <div className="flex justify-between items-center mb-6">
                <div className="flex items-center gap-3">
                  <div className="bg-green-100 p-2 rounded-lg">
                    <FileText className="w-5 h-5 text-green-600" />
                  </div>
                  <div>
                    <h2 className="text-xl font-bold text-gray-800">项目文件</h2>
                    <p className="text-sm text-gray-500">管理您的项目文件和代码</p>
                  </div>
                </div>
                <Button 
                  variant="outline" 
                  className="bg-gradient-to-r from-green-500 to-emerald-600 text-white border-0 hover:from-green-600 hover:to-emerald-700 shadow-lg"
                >
                  <Plus className="w-4 h-4 mr-2" />
                  新建文件
                </Button>
              </div>
              <div className="bg-gradient-to-br from-gray-50 to-gray-100 rounded-xl p-8 text-center border-2 border-dashed border-gray-300">
                <div className="flex flex-col items-center gap-3">
                  <div className="bg-gray-200 p-3 rounded-full">
                    <FileText className="w-8 h-8 text-gray-400" />
                  </div>
                  <div>
                    <p className="text-gray-600 font-medium">欢迎上传您的项目文件</p>
                    <p className="text-sm text-gray-500 mt-1">支持多种文件格式，包括代码、文档等</p>
                  </div>
                  <Button variant="ghost" className="text-blue-600 hover:text-blue-700 hover:bg-blue-50">
                    点击上传或拖拽文件到此处
                  </Button>
                </div>
              </div>
            </div>
          </main>
        </div>
      </div>

      {/* Delete Project Confirmation Dialog */}
      <Dialog open={isDeleteDialogOpen} onOpenChange={setIsDeleteDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>删除项目</DialogTitle>
          </DialogHeader>
          <div className="py-4">
            <p>
              您确定要删除项目 &quot;{projectName}&quot; 吗？
              这将删除所有相关文件且无法撤销。
            </p>
          </div>
          <DialogFooter>
            <Button 
              variant="outline" 
              onClick={() => setIsDeleteDialogOpen(false)}
              disabled={isUpdating}
            >
              取消
            </Button>
            <Button 
              variant="destructive" 
              onClick={handleDeleteProject}
              disabled={isUpdating}
            >
              {isUpdating ? '删除中...' : '删除'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
});
