type Props = {
  name: string;
  filled?: boolean;
  className?: string;
  size?: number;
};

export function MaterialIcon({ name, filled, className, size }: Props) {
  return (
    <span
      className={`material-symbols-outlined${className ? ` ${className}` : ""}`}
      aria-hidden
      style={{
        fontVariationSettings: filled ? "'FILL' 1" : "'FILL' 0",
        ...(size ? { fontSize: size } : {}),
      }}
    >
      {name}
    </span>
  );
}
