import clsx from "clsx";

export function UserMessage({ content, roleLabel }: { content: string; roleLabel: string }) {
  return (
    <div className="flex gap-3 flex-row-reverse">
      <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 text-xs font-bold bg-brand-600 text-white">
        {roleLabel[0].toUpperCase()}
      </div>
      <div className="max-w-[80%]">
        <div className="px-4 py-3 rounded-2xl rounded-br-md text-sm leading-relaxed bg-brand-600 text-white">
          {content}
        </div>
      </div>
    </div>
  );
}
