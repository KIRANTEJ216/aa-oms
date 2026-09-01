"use client";

import { useState, useRef, useEffect } from "react";
import { X, Send, Bot, User, Loader2, MessageSquare, CheckCircle, AlertCircle } from "lucide-react";
import { cn } from "@/lib/utils";
import { SupportAPI, ChatbotMessage, ChatbotResponse } from "@/lib/api";

interface ChatbotProps {
  isOpen?: boolean;
  onClose?: () => void;
}

const QUICK_REPLIES = [
  "Report a bug",
  "Ask about billing",
  "Request a feature",
  "Technical help",
];

export function SupportChatbot({ isOpen = false, onClose }: ChatbotProps) {
  const [messages, setMessages] = useState<Array<{ role: "user" | "bot"; content: string; timestamp: Date; ticketCreated?: boolean }>>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sessionId, setSessionId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    if (isOpen && messages.length === 0) {
      setMessages([{
        role: "bot",
        content: "Hello! I'm your support assistant. How can I help you today? You can report issues, ask questions, or request features.",
        timestamp: new Date(),
      }]);
    }
  }, [isOpen]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setIsLoading(true);

    setMessages(prev => [...prev, { role: "user", content: userMessage, timestamp: new Date() }]);

    try {
      const payload: ChatbotMessage = {
        message: userMessage,
        session_id: sessionId || undefined,
      };

      const response: ChatbotResponse = await SupportAPI.chatbot(payload);
      setSessionId(response.session_id);

      setMessages(prev => [...prev, {
        role: "bot",
        content: response.response,
        timestamp: new Date(),
        ticketCreated: response.ticket_created,
      }]);

      if (response.suggested_actions.length > 0) {
        setTimeout(() => {
          setMessages(prev => [...prev, {
            role: "bot",
            content: "Quick actions:",
            timestamp: new Date(),
            quickReplies: response.suggested_actions,
          }]);
        }, 500);
      }
    } catch (error) {
      setMessages(prev => [...prev, {
        role: "bot",
        content: "Sorry, I encountered an error. Please try again or contact support directly.",
        timestamp: new Date(),
      }]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  const handleQuickReply = (reply: string) => {
    setInput(reply);
    sendMessage();
  };

  if (!isOpen) return null;

  return (
    <div className="fixed bottom-4 right-4 z-50 w-full max-w-sm md:max-w-md">
      <div className="bg-white rounded-xl shadow-xl border border-slate-200 overflow-hidden animate-slide-up">
        {/* Header */}
        <div className="flex items-center justify-between p-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-3">
            <div className="h-10 w-10 rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center">
              <Bot className="h-5 w-5 text-white" />
            </div>
            <div>
              <h3 className="font-semibold text-slate-800">Support Assistant</h3>
              <p className="text-xs text-slate-500">Powered by n8n automation</p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-lg hover:bg-slate-200 transition-colors text-slate-500 hover:text-slate-700"
            aria-label="Close chat"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Messages */}
        <div className="h-[400px] overflow-y-auto p-4 space-y-4" style={{ scrollBehavior: 'smooth' }}>
          {messages.map((msg, idx) => (
            <div key={idx} className={cn("flex gap-3", msg.role === "user" ? "flex-row-reverse" : "")}>
              <div
                className={cn(
                  "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0",
                  msg.role === "user" ? "bg-slate-900 text-white" : "bg-gradient-to-br from-blue-600 to-indigo-600 text-white"
                )}
              >
                {msg.role === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
              </div>
              <div
                className={cn(
                  "max-w-[75%] rounded-2xl px-4 py-2",
                  msg.role === "user"
                    ? "bg-slate-900 text-white rounded-br-none"
                    : "bg-slate-100 text-slate-800 rounded-bl-none"
                )}
              >
                <p className="text-sm whitespace-pre-wrap">{msg.content}</p>
                <p className={cn("text-xs mt-1", msg.role === "user" ? "text-slate-400" : "text-slate-500")}>
                  {msg.timestamp.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                </p>
                {msg.ticketCreated && (
                  <div className="mt-2 flex items-center gap-2 text-xs text-green-700 bg-green-50 px-2 py-1 rounded-full">
                    <CheckCircle className="h-3 w-3" />
                    <span>Support ticket created successfully</span>
                  </div>
                )}
                {(msg as any).quickReplies && (
                  <div className="mt-2 flex flex-wrap gap-2">
                    {((msg as any).quickReplies as string[]).map((reply, i) => (
                      <button
                        key={i}
                        onClick={() => handleQuickReply(reply)}
                        className="text-xs px-3 py-1 bg-white border border-slate-200 rounded-full hover:bg-slate-50 transition-colors"
                      >
                        {reply}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}
          {isLoading && (
            <div className="flex gap-3">
              <div className="h-8 w-8 rounded-full bg-gradient-to-br from-blue-600 to-indigo-600 flex items-center justify-center flex-shrink-0">
                <Bot className="h-4 w-4 text-white" />
              </div>
              <div className="bg-slate-100 rounded-2xl rounded-bl-none px-4 py-2 flex items-center gap-2">
                <Loader2 className="h-4 w-4 text-slate-500 animate-spin" />
                <span className="text-sm text-slate-500">Typing...</span>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Quick Replies (when no messages) */}
        {messages.length <= 1 && !isLoading && (
          <div className="p-4 border-t border-slate-100 bg-slate-50">
            <p className="text-xs text-slate-500 mb-2">Quick start:</p>
            <div className="flex flex-wrap gap-2">
              {QUICK_REPLIES.map((reply) => (
                <button
                  key={reply}
                  onClick={() => handleQuickReply(reply)}
                  className="text-xs px-3 py-1.5 bg-white border border-slate-200 rounded-full hover:bg-slate-50 hover:border-slate-300 transition-colors"
                >
                  {reply}
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Input */}
        <div className="p-4 border-t border-slate-100">
          <div className="flex items-end gap-2">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Type your message..."
              rows={1}
              className="flex-1 px-4 py-2.5 bg-slate-50 border border-slate-200 rounded-xl text-sm focus:outline-none focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20 resize-none"
              disabled={isLoading}
              aria-label="Chat message"
            />
            <button
              onClick={sendMessage}
              disabled={!input.trim() || isLoading}
              className={cn(
                "p-2.5 rounded-xl transition-colors flex-shrink-0",
                input.trim() && !isLoading
                  ? "bg-slate-900 text-white hover:bg-slate-700"
                  : "bg-slate-300 text-slate-500 cursor-not-allowed"
              )}
              aria-label="Send message"
            >
              <Send className="h-5 w-5" />
            </button>
          </div>
          <p className="text-xs text-slate-400 text-center mt-2">
            Press Enter to send, Shift+Enter for new line
          </p>
        </div>
      </div>
    </div>
  );
}

export default SupportChatbot;