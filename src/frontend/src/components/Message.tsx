import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import { User, Bot, Copy, Check } from 'lucide-react';
import { Citations } from './Citations';
import type { Message as MessageType } from '../types';

interface MessageProps {
  message: MessageType;
}

export const Message = ({ message }: MessageProps) => {
  const [copied, setCopied] = useState(false);
  const isUser = message.role === 'user';

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(message.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch (error) {
      console.error('Failed to copy:', error);
    }
  };

  return (
    <div className={`flex gap-5 ${isUser ? 'justify-end' : 'justify-start'} mb-8 animate-in fade-in slide-in-from-bottom-4 duration-500`}>
      {!isUser && (
        <div className="flex-shrink-0 mt-1.5">
          <div className="relative group">
            <div className="absolute inset-0 bg-gradient-to-r from-blue-500 to-purple-500 rounded-full blur-lg opacity-20 group-hover:opacity-30 transition-opacity"></div>
            <div className="relative w-11 h-11 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center shadow-xl">
              <Bot className="w-6 h-6 text-white" strokeWidth={2.5} />
            </div>
          </div>
        </div>
      )}
      
      <div className={`flex flex-col min-w-0 ${isUser ? 'max-w-[75%] items-end' : 'max-w-full flex-1 items-start'}`}>
        <div
          className={`relative group rounded-3xl shadow-2xl transition-all duration-300 w-full ${
            isUser
              ? 'bg-gradient-to-br from-[#6366f1] via-[#7c3aed] to-[#8b5cf6] text-white px-6 py-4'
              : message.isError
              ? 'bg-red-950/30 border border-red-800/50 text-red-200 backdrop-blur-sm px-6 py-4'
              : 'bg-[#1a1a1a] border border-gray-800/50 px-7 py-5'
          }`}
        >
          {!isUser && !message.isError && (
            <button
              onClick={handleCopy}
              className="absolute top-3 right-3 opacity-0 group-hover:opacity-100 transition-all duration-200 p-2 rounded-lg hover:bg-white/10 backdrop-blur-sm z-10"
              title="Copy message"
            >
              {copied ? (
                <Check className="w-4 h-4 text-green-400" strokeWidth={2.5} />
              ) : (
                <Copy className="w-4 h-4 text-gray-400" strokeWidth={2} />
              )}
            </button>
          )}
          
          {isUser ? (
            <p className="text-base leading-[1.7] whitespace-pre-wrap break-words font-normal">
              {message.content}
            </p>
          ) : (
            <div className="w-full overflow-hidden">
              <div className="markdown-content text-base leading-[1.8] break-words text-gray-200">
                <ReactMarkdown>{message.content}</ReactMarkdown>
              </div>
              {message.citations && message.citations.length > 0 && (
                <div className="mt-6">
                  <Citations citations={message.citations} />
                </div>
              )}
            </div>
          )}
        </div>
        
        <span className="text-[10px] text-gray-600 mt-2 px-1 font-medium uppercase tracking-wider">
          {message.timestamp.toLocaleTimeString([], { 
            hour: '2-digit', 
            minute: '2-digit' 
          })}
        </span>
      </div>

      {isUser && (
        <div className="flex-shrink-0 mt-1.5">
          <div className="w-11 h-11 rounded-full bg-gradient-to-br from-gray-700 to-gray-800 flex items-center justify-center shadow-xl border border-gray-700/50">
            <User className="w-6 h-6 text-gray-300" strokeWidth={2.5} />
          </div>
        </div>
      )}
    </div>
  );
};
