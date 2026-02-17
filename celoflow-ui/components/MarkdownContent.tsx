import React from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

interface MarkdownContentProps {
  content: string;
  className?: string;
}

/**
 * Renders markdown content with proper styling for chat messages.
 * Supports GFM (tables, strikethrough, task lists, autolinks).
 */
export const MarkdownContent: React.FC<MarkdownContentProps> = ({ content, className = '' }) => {
  return (
    <div className={`markdown-content ${className}`}>
    <ReactMarkdown
      remarkPlugins={[remarkGfm]}
      components={{
        // Headings
        h1: ({ children }) => <h1 className="text-xl font-bold mt-4 mb-2 first:mt-0">{children}</h1>,
        h2: ({ children }) => <h2 className="text-lg font-bold mt-3 mb-2 first:mt-0">{children}</h2>,
        h3: ({ children }) => <h3 className="text-base font-bold mt-3 mb-1 first:mt-0">{children}</h3>,

        // Paragraphs
        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,

        // Lists
        ul: ({ children }) => <ul className="list-disc list-inside mb-2 space-y-1 ml-1">{children}</ul>,
        ol: ({ children }) => <ol className="list-decimal list-inside mb-2 space-y-1 ml-1">{children}</ol>,
        li: ({ children }) => <li className="leading-relaxed">{children}</li>,

        // Inline code
        code: ({ className: codeClassName, children, ...props }) => {
          const isBlock = codeClassName?.startsWith('language-');
          if (isBlock) {
            return (
              <code className={`block bg-gray-900 text-gray-100 rounded-lg p-3 my-2 text-xs font-mono overflow-x-auto whitespace-pre ${codeClassName}`} {...props}>
                {children}
              </code>
            );
          }
          return (
            <code className="bg-gray-200 dark:bg-gray-600 text-pink-600 dark:text-pink-300 px-1.5 py-0.5 rounded text-xs font-mono" {...props}>
              {children}
            </code>
          );
        },

        // Code blocks (pre wrapper)
        pre: ({ children }) => <pre className="my-2 overflow-hidden rounded-lg">{children}</pre>,

        // Links
        a: ({ href, children }) => (
          <a href={href} target="_blank" rel="noopener noreferrer" className="text-blue-600 dark:text-blue-400 underline hover:text-blue-800 dark:hover:text-blue-300 transition-colors">
            {children}
          </a>
        ),

        // Bold & italic (handled automatically by markdown)

        // Blockquotes
        blockquote: ({ children }) => (
          <blockquote className="border-l-3 border-celo-green pl-3 my-2 text-gray-600 dark:text-gray-400 italic">
            {children}
          </blockquote>
        ),

        // Horizontal rules
        hr: () => <hr className="my-3 border-gray-200 dark:border-gray-600" />,

        // Tables
        table: ({ children }) => (
          <div className="overflow-x-auto my-2">
            <table className="min-w-full text-xs border-collapse">{children}</table>
          </div>
        ),
        thead: ({ children }) => <thead className="bg-gray-100 dark:bg-gray-600">{children}</thead>,
        th: ({ children }) => <th className="px-2 py-1.5 text-left font-semibold border border-gray-200 dark:border-gray-500">{children}</th>,
        td: ({ children }) => <td className="px-2 py-1.5 border border-gray-200 dark:border-gray-600">{children}</td>,

        // Strong & emphasis
        strong: ({ children }) => <strong className="font-bold">{children}</strong>,
        em: ({ children }) => <em className="italic">{children}</em>,
      }}
    >
      {content}
    </ReactMarkdown>
    </div>
  );
};
