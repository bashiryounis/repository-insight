import {
  useState,
  useEffect,
  useRef,
  useCallback,
  useLayoutEffect,
} from 'react';
import { BiPlus, BiUser, BiSend, BiSolidUserCircle } from 'react-icons/bi';
import { MdOutlineArrowLeft, MdOutlineArrowRight } from 'react-icons/md';
import ReactMarkdown from 'react-markdown';

const WS_URL = import.meta.env.VITE_WS_URL;

function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState([]);
  const [currentTitle, setCurrentTitle] = useState(null);
  const [isResponseLoading, setIsResponseLoading] = useState(false);
  const [errorText, setErrorText] = useState('');
  const [isShowSidebar, setIsShowSidebar] = useState(false);
  const scrollToLastItem = useRef(null);
  const ws = useRef(null);
  const isEmpty = messages.length === 0 && !currentTitle;

  const connectWebSocket = useCallback(() => {
    ws.current = new WebSocket(WS_URL);

    ws.current.onopen = () => {
      console.log('✅ WS connected');
      setErrorText('');
    };

    ws.current.onmessage = (evt) => {
      const data = JSON.parse(evt.data);
      if (data.type === 'stream') {
        // append token to the last assistant message
        setMessages(prev => {
          const copy = [...prev];
          copy[copy.length - 1].content += data.payload;
          return copy;
        });
      }

      else if (data.type === 'final_result') {
        // nothing to do here if you streamed continuously,
        // or you could overwrite with the full answer:
        // setMessages(prev => {
        //   const copy = [...prev];
        //   copy[copy.length - 1].content = data.payload;
        //   return copy;
        // });
      }
      else if (data.type === 'error') {
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
    setCurrentTitle(null);
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
    setTimeout(() => scrollToLastItem.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth' }), 100);
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

  // Effect to scroll to the latest message when new content is streamed
  useEffect(() => {
    if (messages.length > 0) {
      scrollToLastItem.current?.lastElementChild?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [messages]);

  return (
    <div className='container'>
      <section className={`sidebar ${isShowSidebar ? 'open' : ''}`}>
        <div className='sidebar-header' onClick={createNewChat} role='button'>
          <BiPlus size={20} />
          <button>New Chat</button>
        </div>
        {/* <div className='sidebar-info'>
          <div className='sidebar-info-upgrade'>
            <BiUser size={20} />
            <p>Upgrade plan</p>
          </div>
          <div className='sidebar-info-user'>
            <BiSolidUserCircle size={20} />
            <p>User</p>
          </div>
        </div> */}
      </section>

      <section className={`main ${isEmpty ? 'main--empty' : 'main--with-messages'}`}>
        {!currentTitle && messages.length === 0 && (
          <div className='empty-chat-container'>
            {/* <img src='images/logo.svg' width={45} height={45} alt='Repository Insights' /> */}
            <h1>Repository Insight Service</h1>
            <h3>Let's get deeper into your repository</h3>
          </div>
        )}

        {isShowSidebar ? (
          <MdOutlineArrowRight className='burger' size={28.8} onClick={toggleSidebar} />
        ) : (
          <MdOutlineArrowLeft className='burger' size={28.8} onClick={toggleSidebar} />
        )}

        <div className='main-header'>
          <ul>
            {messages.map((chatMsg, idx) => (
              <li key={idx} ref={scrollToLastItem}>
                {/* <div> */}
                  <div className="message-content">
                    <ReactMarkdown>{chatMsg.content}</ReactMarkdown>
                  </div>
                {/* </div> */}
              </li>
            ))}
          </ul>
        </div>

        <div className='main-bottom'>
          {errorText && <p className='errorText'>{errorText}</p>}
          <form className='form-container' onSubmit={submitHandler}>
            <input
              type='text'
              placeholder='Send a message.'
              spellCheck='false'
              value={isResponseLoading ? 'Processing...' : text}
              onChange={(e) => setText(e.target.value)}
              readOnly={isResponseLoading}
            />
            {!isResponseLoading && (
              <button type='submit'>
                <BiSend size={20} />
              </button>
            )}
          </form>
          <p>Repository Insight may generate approximations. Always verify your findings.</p>
        </div>
      </section>
    </div>
  );
}

export default App;