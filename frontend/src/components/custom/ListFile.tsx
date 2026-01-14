import { X, FileText, Image as ImageIcon } from "lucide-react";

type Props = {
  files: File[] | string[] | null;
  onRemove?: (index: number) => void; // opcional
};

export default function ListFile({ files, onRemove }: Props) {
  const normalizeName = (f: File | string) => (f instanceof File ? f.name : f);

  const getIcon = (name: string) => {
    const ext = name.split(".").pop()?.toLowerCase();

    if (["png", "jpg", "jpeg", "gif", "webp"].includes(ext ?? "")) {
      return <ImageIcon size={18} />;
    }

    return <FileText size={18} />;
  };

  return (
    <div className="flex flex-wrap gap-2">
      {files?.map((file, index) => {
        const fileName = normalizeName(file);

        return (
          <div
            key={fileName + index}
            title={fileName}
            className="flex items-center gap-2 px-3 py-1.5
                       bg-white dark:bg-zinc-800
                       border border-zinc-300 dark:border-zinc-700
                       rounded-lg shadow-sm hover:shadow-md transition
                       max-w-[250px] overflow-hidden"
          >
            <div className="text-zinc-600 dark:text-zinc-300">
              {getIcon(fileName)}
            </div>

            <span className="text-sm truncate flex-1">{fileName}</span>

            {onRemove && (
              <button
                onClick={() => onRemove(index)}
                className="text-red-500 hover:text-red-700 transition"
              >
                <X size={14} />
              </button>
            )}
          </div>
        );
      })}
    </div>
  );
}
