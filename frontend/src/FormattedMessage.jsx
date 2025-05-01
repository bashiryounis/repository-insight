import React from 'react';
import { BiCopy } from 'react-icons/bi';

function CodeBlock({ language, content }) {
  const handleCopy = () => navigator.clipboard.writeText(content);

  return (
    <div className="code-block">
      <div className="code-header">
        <span className="code-language">{language || 'text'}</span>
        <button className="code-action" onClick={handleCopy} title="Copy code">
          <BiCopy size={14} /> Copy
        </button>
      </div>
      <pre><code>{content}</code></pre>
    </div>
  );
}

export default function FormattedMessage({ content }) {
  const blocks = [];
  const lines = content.split('\n');
  let inCode = false;
  let codeLang = '';
  let codeBuffer = [];

  lines.forEach((line, i) => {
    if (line.startsWith('```')) {
      if (inCode) {
        // End code block
        blocks.push(<CodeBlock key={`code-${i}`} language={codeLang} content={codeBuffer.join('\n')} />);
        codeBuffer = [];
        codeLang = '';
        inCode = false;
      } else {
        // Start code block
        codeLang = line.replace('```', '').trim();
        inCode = true;
      }
    } else if (inCode) {
      codeBuffer.push(line);
    } else {
      blocks.push(<p key={`line-${i}`}>{line}</p>);
    }
  });

  return <div className="formatted-message">{blocks}</div>;
}
