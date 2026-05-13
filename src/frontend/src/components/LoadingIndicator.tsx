import { Bot } from 'lucide-react';

export const LoadingIndicator = () => {
  return (
    <div className="flex gap-5 mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500">
      <div className="flex-shrink-0 mt-1.5">
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full blur-lg opacity-20 animate-pulse"></div>
          <div className="relative w-11 h-11 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-xl">
            <Bot className="w-6 h-6 text-white animate-pulse" strokeWidth={2.5} />
          </div>
        </div>
      </div>
      
      <div className="flex flex-col flex-1">
        <div className="bg-[#1a1a1a] border border-gray-800/50 rounded-3xl px-7 py-5 shadow-2xl">
          <div className="flex items-center gap-3">
            <div className="flex gap-2">
              <div className="w-2.5 h-2.5 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms', animationDuration: '1s' }}></div>
              <div className="w-2.5 h-2.5 bg-purple-500 rounded-full animate-bounce" style={{ animationDelay: '200ms', animationDuration: '1s' }}></div>
              <div className="w-2.5 h-2.5 bg-pink-500 rounded-full animate-bounce" style={{ animationDelay: '400ms', animationDuration: '1s' }}></div>
            </div>
            <span className="text-sm text-gray-400 font-medium ml-1">Analyzing documents...</span>
          </div>
        </div>
      </div>
    </div>
  );
};
