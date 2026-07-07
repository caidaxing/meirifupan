import { useState, useRef, useEffect } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

interface Message {
  role: "user" | "ai";
  content: string;
  timestamp?: string;
}

const API_URL = "";  // 使用 vite 代理

// 快捷问题
const QUICK_QUESTIONS = [
  "今天行情怎么样",
  "市场情绪如何",
  "今天涨停多少只",
  "哪些板块涨得好",
  "热门股票有哪些",
  "今天跌停多少",
];

export default function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (text?: string) => {
    const question = (text || input).trim();
    if (!question || loading) return;

    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: question }]);
    setLoading(true);

    try {
      const res = await fetch(`${API_URL}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question }),
      });
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: data.reply, timestamp: data.timestamp },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "ai", content: "请求失败，请检查后端是否运行" },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const clearChat = () => {
    setMessages([]);
  };

  return (
    <div style={styles.container}>
      {/* 头部 */}
      <div style={styles.header}>
        <div style={styles.headerLeft}>
          <span style={styles.logo}>📈</span>
          <div>
            <h1 style={styles.title}>A股智能问答助手</h1>
            <span style={styles.subtitle}>涨停 · 板块 · 情绪 · 个股</span>
          </div>
        </div>
        <button style={styles.clearBtn} onClick={clearChat}>
          清空对话
        </button>
      </div>

      {/* 聊天区域 */}
      <div style={styles.chat}>
        {messages.length === 0 && (
          <div style={styles.empty}>
            <div style={styles.emptyIcon}>🤖</div>
            <p style={styles.emptyTitle}>你好，我是 A 股问答助手</p>
            <p style={styles.emptyDesc}>问我任何关于 A 股的问题</p>

            <div style={styles.quickQuestions}>
              {QUICK_QUESTIONS.map((q) => (
                <button
                  key={q}
                  style={styles.quickBtn}
                  onClick={() => send(q)}
                >
                  {q}
                </button>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div
            key={i}
            style={{
              ...styles.messageWrap,
              justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
            }}
          >
            {msg.role === "ai" && <span style={styles.avatar}>🤖</span>}
            <div
              style={{
                ...styles.message,
                ...(msg.role === "user" ? styles.userMessage : styles.aiMessage),
              }}
            >
              {msg.role === "ai" ? (
                <div className="markdown-body">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>
                    {msg.content}
                  </ReactMarkdown>
                </div>
              ) : (
                msg.content
              )}
            </div>
            {msg.role === "user" && <span style={styles.avatar}>👤</span>}
          </div>
        ))}

        {loading && (
          <div style={{ ...styles.messageWrap, justifyContent: "flex-start" }}>
            <span style={styles.avatar}>🤖</span>
            <div style={{ ...styles.message, ...styles.aiMessage, color: "#888" }}>
              <span className="loading-dots">思考中</span>
            </div>
          </div>
        )}

        <div ref={chatEndRef} />
      </div>

      {/* 输入区域 */}
      <div style={styles.inputBar}>
        <input
          style={styles.input}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => e.key === "Enter" && send()}
          placeholder="输入问题，如：今天行情怎么样"
          disabled={loading}
        />
        <button
          style={{
            ...styles.sendBtn,
            opacity: loading ? 0.6 : 1,
          }}
          onClick={() => send()}
          disabled={loading}
        >
          发送
        </button>
      </div>
    </div>
  );
}

const styles: Record<string, React.CSSProperties> = {
  container: {
    maxWidth: 800,
    margin: "0 auto",
    height: "100vh",
    display: "flex",
    flexDirection: "column",
    fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    background: "#f5f5f5",
  },
  header: {
    padding: "16px 20px",
    background: "#1a1a2e",
    color: "#fff",
    display: "flex",
    justifyContent: "space-between",
    alignItems: "center",
  },
  headerLeft: {
    display: "flex",
    alignItems: "center",
    gap: 12,
  },
  logo: {
    fontSize: 28,
  },
  title: {
    margin: 0,
    fontSize: 18,
    fontWeight: 600,
  },
  subtitle: {
    fontSize: 12,
    color: "#aaa",
  },
  clearBtn: {
    padding: "6px 12px",
    background: "rgba(255,255,255,0.1)",
    color: "#fff",
    border: "none",
    borderRadius: 6,
    cursor: "pointer",
    fontSize: 13,
  },
  chat: {
    flex: 1,
    overflowY: "auto",
    padding: 20,
    display: "flex",
    flexDirection: "column",
    gap: 16,
  },
  empty: {
    textAlign: "center" as const,
    marginTop: 60,
  },
  emptyIcon: {
    fontSize: 48,
    marginBottom: 16,
  },
  emptyTitle: {
    fontSize: 20,
    fontWeight: 600,
    color: "#333",
    margin: "0 0 8px",
  },
  emptyDesc: {
    fontSize: 14,
    color: "#888",
    margin: "0 0 24px",
  },
  quickQuestions: {
    display: "flex",
    flexWrap: "wrap" as const,
    gap: 8,
    justifyContent: "center",
  },
  quickBtn: {
    padding: "8px 16px",
    background: "#fff",
    border: "1px solid #e0e0e0",
    borderRadius: 20,
    cursor: "pointer",
    fontSize: 14,
    color: "#333",
    transition: "all 0.2s",
  },
  messageWrap: {
    display: "flex",
    alignItems: "flex-start",
    gap: 8,
  },
  avatar: {
    fontSize: 24,
    marginTop: 4,
  },
  message: {
    maxWidth: "70%",
    padding: "12px 16px",
    borderRadius: 16,
    fontSize: 15,
    lineHeight: 1.6,
  },
  userMessage: {
    background: "#007AFF",
    color: "#fff",
    borderBottomRightRadius: 4,
  },
  aiMessage: {
    background: "#fff",
    color: "#333",
    borderBottomLeftRadius: 4,
    boxShadow: "0 1px 2px rgba(0,0,0,0.1)",
  },
  inputBar: {
    display: "flex",
    gap: 10,
    padding: "16px 20px",
    background: "#fff",
    borderTop: "1px solid #e0e0e0",
  },
  input: {
    flex: 1,
    padding: "12px 16px",
    border: "1px solid #e0e0e0",
    borderRadius: 24,
    fontSize: 15,
    outline: "none",
  },
  sendBtn: {
    padding: "12px 24px",
    background: "#007AFF",
    color: "#fff",
    border: "none",
    borderRadius: 24,
    fontSize: 15,
    cursor: "pointer",
    fontWeight: 600,
  },
};
