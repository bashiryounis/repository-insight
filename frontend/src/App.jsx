import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useLayoutEffect,
} from 'react';
import { BiPlus, BiSend, BiCodeAlt } from 'react-icons/bi';
import { BiMenu, BiX } from 'react-icons/bi';
import FormattedMessage from './FormattedMessage';

const WS_URL = import.meta.env.VITE_WS_URL;

function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState([]);
  const [isResponseLoading, setIsResponseLoading] = useState(false);
  const [errorText, setErrorText] = useState('');
  const [isShowSidebar, setIsShowSidebar] = useState(false);
  const scrollToLastItem = useRef(null);
  const ws = useRef(null);
  const SERVICE_NAME = 'Repository Insight AI';
  const [theme, setTheme] = useState(localStorage.getItem('theme') || 'light');

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('theme', theme);
  }, [theme]);

  const toggleTheme = () => {
    setTheme(prev => (prev === 'light' ? 'dark' : 'light'));
  };


  const connectWebSocket = useCallback(() => {
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      console.log('✅ WS connected');
      setErrorText('');
    };

    ws.current.onmessage = (evt) => {
      const data = JSON.parse(evt.data);
      if (data.type === 'stream') {
        setMessages((prev) => {
          const copy = [...prev];
          copy[copy.length - 1].content += data.payload;
          return copy;
        });
      } else if (data.type === 'error') {
        setErrorText(data.payload);
      }
    };

    ws.current.onerror = () => {
      console.error('⚠️ WS error');
      setErrorText('WebSocket connection error');
    };

    ws.current.onclose = (evt) => {
      console.log('🔒 WS closed', evt);
      if (!evt.wasClean) {
        setErrorText(`WebSocket closed unexpectedly (code=${evt.code})`);
      }
    };
  }, []);

  useEffect(() => {
    connectWebSocket();
    return () => ws.current?.close();
  }, [connectWebSocket]);

  const createNewChat = () => {
    setMessages([]);
    setText('');
  };

  const toggleSidebar = useCallback(() => {
    setIsShowSidebar((prev) => !prev);
  }, []);

  const submitHandler = (e) => {
    e.preventDefault();
    if (!text) return;

    setIsResponseLoading(true);
    setErrorText('');

    const userMessage = { role: 'user', content: text };
    const assistantMessage = { role: 'assistant', content: '' };

    setMessages((prev) => [...prev, userMessage, assistantMessage]);
    ws.current.send(JSON.stringify({ query: text }));
    setText('');
    setTimeout(() => {
      scrollToLastItem.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth' });
    }, 100);
    setIsResponseLoading(false);
  };

  useLayoutEffect(() => {
    const handleResize = () => {
      setIsShowSidebar(window.innerWidth <= 640);
    };
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  useEffect(() => {
    if (messages.length > 0) {
      scrollToLastItem.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <div className={`app-container ${isShowSidebar ? 'sidebar-hidden' : ''}`}>
      <div className={`sidebar ${isShowSidebar ? 'open' : ''}`}>
      <div className="logo">
      </div>


        <button className="new-chat-btn">
          <span className="btn-icon">
            <BiPlus size={16} />
          </span>
          <span>New Chat</span>
        </button>


        <div className="project-selector">
          <div className="project-label">Current Project</div>
          <select className="project-dropdown" value="personal" readOnly>
            <option value="personal">Personal Workspace</option>
          </select>
        </div>

        <div className="project-history">
          <div className="history-title">Recent Chats</div>
          <div className="history-item active">{SERVICE_NAME}</div>
        </div>

        <div className="sidebar-footer">Help & Resources</div>
      </div>

      <div className="main-content">
        <div className="top-bar">
          <div className="conversation-title">
             {SERVICE_NAME}
          </div>
          <div className="conversation-actions">
          <button className="theme-toggle" onClick={toggleTheme} title="Toggle Theme">
            {theme === 'dark' ? (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
              </svg>
            ) : (
              <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="5" />
                <line x1="12" y1="1" x2="12" y2="3" />
                <line x1="12" y1="21" x2="12" y2="23" />
                <line x1="4.22" y1="4.22" x2="5.64" y2="5.64" />
                <line x1="18.36" y1="18.36" x2="19.78" y2="19.78" />
                <line x1="1" y1="12" x2="3" y2="12" />
                <line x1="21" y1="12" x2="23" y2="12" />
                <line x1="4.22" y1="19.78" x2="5.64" y2="18.36" />
                <line x1="18.36" y1="5.64" x2="19.78" y2="4.22" />
              </svg>
            )}
          </button>

          <button className="sidebar-toggle" onClick={toggleSidebar} title="Toggle Sidebar">
            {isShowSidebar ? <BiMenu size={22} /> : <BiX size={22} />}
          </button>
          </div>
        </div>

        <div className="chat-container" ref={scrollToLastItem}>
          {messages.map((msg, idx) => (
            <div key={idx} className={`message ${msg.role}`}>
              <div className="message-avatar">
                  {msg.role === 'user' ? (
                  <span className="user-avatar">U</span>
                ) : (
                  <svg
                    xmlns="http://www.w3.org/2000/svg"
                    width="24"
                    height="24"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="repository-logo"
                  >
                    <polyline points="16 18 22 12 16 6" />
                    <polyline points="8 6 2 12 8 18" />
                  </svg>
                )}
              </div>
              <div className="message-content">
                <div className="message-text">
                  <FormattedMessage content={msg.content} />
                </div>
              </div>
            </div>
          ))}
        </div>

        <div className="input-container">
          <div className="input-form">
            <div className="input-header">
              <button className="input-type-btn active">Text</button>
              <button className="input-type-btn">URL</button>
            </div>

            <form className="input-area" onSubmit={submitHandler}>
              <textarea
                className="input-textarea"
                placeholder="Ask a coding question or paste code..."
                value={isResponseLoading ? 'Processing...' : text}
                onChange={(e) => setText(e.target.value)}
                readOnly={isResponseLoading}
              />
              <div className="input-actions">
                <button type="submit" className="send-btn">
                  <BiSend />
                  Send
                </button>
              </div>
            </form>
          </div>
          <div className="keyboard-shortcuts">
            Press Enter to send, Shift+Enter for new line
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
