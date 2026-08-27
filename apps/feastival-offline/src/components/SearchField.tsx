import { useEffect, useRef, useState } from "react";

type Props = {
  value: string;
  placeholder: string;
  onCommit: (next: string) => void;
};

export function SearchField({ value, placeholder, onCommit }: Props) {
  const [text, setText] = useState(value);
  const commit = useRef(onCommit);
  commit.current = onCommit;
  useEffect(() => {
    setText(value);
  }, [value]);
  useEffect(() => {
    const t = window.setTimeout(() => {
      if (text !== value) commit.current(text);
    }, 250);
    return () => window.clearTimeout(t);
  }, [text, value]);
  return (
    <input
      className="search"
      placeholder={placeholder}
      value={text}
      onChange={(e) => setText(e.target.value)}
    />
  );
}
