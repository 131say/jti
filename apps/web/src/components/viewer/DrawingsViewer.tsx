"use client";

function filenameFromArtifactUrl(url: string): string {
  try {
    const path = new URL(url).pathname.split("/").pop() ?? "";
    return decodeURIComponent(path || url);
  } catch {
    return url;
  }
}

export function DrawingsViewer({
  urls,
  zipUrl,
}: {
  urls: string[];
  zipUrl?: string | null;
}) {
  if (urls.length === 0) {
    return (
      <p className="text-[11px] text-neutral-500">
        Нет сгенерированных SVG. Проверьте предупреждения воркера или повторите
        генерацию.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-[11px] leading-relaxed text-amber-200/90">
        Автоматические размеры пока не поддерживаются. Представлена только
        базовая геометрия контуров.
      </p>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {urls.map((u) => (
          <figure
            key={u}
            className="rounded border border-neutral-800 bg-neutral-900/50 p-2"
          >
            <img
              src={u}
              alt=""
              className="max-h-[240px] w-full cursor-zoom-in object-contain"
              onClick={() => window.open(u, "_blank", "noopener,noreferrer")}
            />
            <figcaption className="mt-1 truncate text-center text-[10px] text-neutral-500">
              {filenameFromArtifactUrl(u)}
            </figcaption>
          </figure>
        ))}
      </div>
      {zipUrl ? (
        <a
          href={zipUrl}
          className="inline-flex w-fit items-center rounded border border-neutral-600 px-3 py-1.5 text-[11px] text-neutral-200 hover:bg-neutral-800"
        >
          Скачать все чертежи (в составе project.zip)
        </a>
      ) : null}
    </div>
  );
}
