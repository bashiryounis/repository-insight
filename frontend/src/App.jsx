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

function App() {
  const [text, setText] = useState('');
  const [messages, setMessages] = useState([]);
  const [currentTitle, setCurrentTitle] = useState(null);
  const [isResponseLoading, setIsResponseLoading] = useState(false);
  const [errorText, setErrorText] = useState('');
  const [isShowSidebar, setIsShowSidebar] = useState(false);
  const scrollToLastItem = useRef(null);
  const ws = useRef(null);

  const connectWebSocket = useCallback(() => {
    ws.current = new WebSocket('wss://your-websocket-endpoint');

    ws.current.onmessage = (event) => {
      const data = JSON.parse(event.data);
      setMessages((prev) => [
        ...prev.slice(0, -1),
        { ...prev[prev.length - 1], content: prev[prev.length - 1].content + data.chunk }
      ]);
    };

    ws.current.onerror = (err) => {
      setErrorText("WebSocket error: " + err.message);
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
    ws.current.send(JSON.stringify({ message: text }));
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

      <section className='main'>
        {!currentTitle && (
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
                {chatMsg.role === 'user' ? (
                  <div><BiSolidUserCircle size={28.8} /></div>
                ) : (
                  <img src='images/logo.svg' alt='Assistant' />
                )}
                <div>
                  <p className='role-title'>{chatMsg.role === 'user' ? 'You' : 'Assistant'}</p>
                  <ReactMarkdown>{chatMsg.content}</ReactMarkdown>
                </div>
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
