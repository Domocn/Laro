import { useEffect, useState } from "react";

type Props = {
  value: string;
  placeholder: string;
  onChange: (next: string) => void;
};

/** Local-first search: parent filters on every change; URL sync is the parent's job on idle/blur. */
export function SearchField({ value, placeholder, onChange }: Props) {
  const [text, setText] = useState(value);
  useEffect(() => {
    setText(value);
  }, [value]);
  return (
    <input
      className="search"
      placeholder={placeholder}
      value={text}
      onChange={(e) => {
        const next = e.target.value;
        setText(next);
        onChange(next);
      }}
    />
  );
}
