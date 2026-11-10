import { Fragment, type ReactNode } from "react";

/**
 * Renders docs/policy.md: headings, paragraphs, numbered lists, tables, **bold** and `code`.
 * The text is ours, but it still goes through React elements, never through innerHTML.
 */
export function PolicyDocument({ markdown }: { markdown: string }) {
  const blocks = markdown.trim().split(/\n{2,}/);
  return (
    <div className="flex flex-col gap-4">
      {blocks.map((block, index) => renderBlock(block, index))}
    </div>
  );
}

function renderBlock(block: string, key: number): ReactNode {
  const lines = block.split("\n");
  const first = lines[0] ?? "";
  if (first.startsWith("# ")) {
    return (
      <h1 key={key} className="text-h1">
        {inline(first.slice(2))}
      </h1>
    );
  }
  if (first.startsWith("## ")) {
    return (
      <h2 key={key} className="text-h2 pt-4">
        {inline(first.slice(3))}
      </h2>
    );
  }
  if (first.startsWith("|")) return renderTable(lines, key);
  if (/^\d+\.\s/.test(first)) {
    return (
      <ol key={key} className="flex list-decimal flex-col gap-2 pl-6">
        {lines.map((line, index) => (
          <li key={index}>{inline(line.replace(/^\d+\.\s/, ""))}</li>
        ))}
      </ol>
    );
  }
  return (
    <p key={key} className="text-text2">
      {inline(lines.join(" "))}
    </p>
  );
}

function cells(line: string): string[] {
  return line
    .replace(/^\||\|$/g, "")
    .split("|")
    .map((cell) => cell.trim());
}

function renderTable(lines: string[], key: number): ReactNode {
  const [head = "", , ...rows] = lines;
  return (
    <div key={key} className="border-border overflow-x-auto rounded-lg border">
      <table className="w-full border-collapse text-left">
        <thead className="bg-sunken text-label">
          <tr>
            {cells(head).map((cell, index) => (
              <th key={index} scope="col" className="px-3 py-2">
                {inline(cell)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr key={rowIndex} className="border-border border-t align-top">
              {cells(row).map((cell, index) => (
                <td key={index} className="text-text2 px-3 py-2">
                  {inline(cell)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function inline(text: string): ReactNode {
  return text.split(/(\*\*[^*]+\*\*|`[^`]+`)/).map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return (
        <strong key={index} className="text-text font-semibold">
          {part.slice(2, -2)}
        </strong>
      );
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={index} className="text-mono font-mono">
          {part.slice(1, -1)}
        </code>
      );
    }
    return <Fragment key={index}>{part}</Fragment>;
  });
}
