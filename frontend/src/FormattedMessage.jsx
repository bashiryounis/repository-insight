import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
// import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { BiCopy, BiCheck } from "react-icons/bi";
import { PrismLight as SyntaxHighlighter } from "react-syntax-highlighter";
import python from "react-syntax-highlighter/dist/esm/languages/prism/python";
SyntaxHighlighter.registerLanguage("python", python);


const getTheme = () =>
  typeof document !== "undefined" &&
  document.documentElement.getAttribute("data-theme") === "dark";

const languageMap = {
  js: "javascript",
  ts: "typescript",
  py: "python",
  sh: "bash",
  yml: "yaml",
  md: "markdown",
  rb: "ruby",
  cpp: "cpp",
  c: "c",
  cs: "csharp",
  html: "html",
  css: "css",
  json: "json",
  java: "java",
  php: "php",
  go: "go",
  rust: "rust",
};

export default function FormattedMessage({ text = "" }) {
  return (
    <div className="prose prose-zinc dark:prose-invert max-w-none">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code: MarkdownCode,
          table: Table,
          thead: TableHead,
          tbody: TableBody,
          tr: TableRow,
          th: TableHeader,
          td: TableCell,
        }}
      >
        {text}
      </ReactMarkdown>
    </div>
  );
}

function MarkdownCode({ inline, className, children = [], ...props }) {
  const rawLang = className?.replace("language-", "") || "";
  const language = languageMap[rawLang] || rawLang || "";
  const code = Array.isArray(children)
    ? children.join("").trim()
    : String(children).trim();

  const isProbablyCode = className?.startsWith("language-");

  if (inline || (!isProbablyCode && !code.includes("\n"))) {
    return <code className="inline-code">{code}</code>;
  }

  const [copied, setCopied] = useState(false);
  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="code-block relative rounded-xl overflow-auto w-full max-w-full mb-6">
      <div className="code-header">
        <span className="code-language">{language}</span>
        <div className="code-actions">
          <button onClick={handleCopy} className="code-action">
            {copied ? (
              <>
                <BiCheck size={16} />
                <span>Copied</span>
              </>
            ) : (
              <>
                <BiCopy size={14} />
                <span>Copy</span>
              </>
            )}
          </button>
        </div>
      </div>
      <SyntaxHighlighter
        language={language}
        // style={undefined} // ✅ Don't use Prism theme colors
        useInlineStyles={false} 
        className="code-block"
        PreTag="div"
        CodeTag="code"
        customStyle={{
          margin: 0,
          padding: '0.75rem 1rem',
          background: 'transparent',
          minWidth: '100%',
        }}
        wrapLongLines
        showLineNumbers={false}
        {...props}
      >
        {code}
      </SyntaxHighlighter>
    </div>
  );
}


function Table({ children }) {
  return (
    <div className="overflow-x-auto my-4">
      <table className="min-w-full border-collapse border border-gray-300 dark:border-gray-700 rounded-lg">
        {children}
      </table>
    </div>
  );
}
function TableHead({ children }) {
  return <thead className="bg-gray-100 dark:bg-gray-800">{children}</thead>;
}
function TableBody({ children }) {
  return <tbody>{children}</tbody>;
}
function TableRow({ children }) {
  return <tr className="border-b border-gray-300 dark:border-gray-700">{children}</tr>;
}
function TableHeader({ children }) {
  return (
    <th className="py-3 px-4 text-left font-semibold border-r border-gray-300 dark:border-gray-700 last:border-r-0">
      {children}
    </th>
  );
}
function TableCell({ children }) {
  return (
    <td className="py-2 px-4 border-r border-gray-300 dark:border-gray-700 last:border-r-0">
      {children}
    </td>
  );
}
