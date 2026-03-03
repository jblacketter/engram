interface TagBadgeProps {
  tag: string;
  onClick?: () => void;
}

export default function TagBadge({ tag, onClick }: TagBadgeProps) {
  return (
    <span
      onClick={onClick}
      className={`inline-block px-2 py-0.5 text-xs font-medium rounded-full bg-blue-100 text-blue-800 ${
        onClick ? "cursor-pointer hover:bg-blue-200" : ""
      }`}
    >
      {tag}
    </span>
  );
}
