interface TopbarProps {
  title: string;
}

export default function Topbar({ title }: TopbarProps) {
  return (
    <header className="h-14 bg-card border-b border-border flex items-center px-6">
      <h1 className="text-xl font-semibold text-foreground">{title}</h1>
    </header>
  );
}
