import { useState } from "react";
import { Placeholder } from "./primitives";
/** Editorial reference only. Never represents generated frames or recognition output. */
export function ReferenceImage({
  src,
  alt,
  caption,
  className = "",
}: {
  src: string;
  alt: string;
  caption: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  return (
    <figure className={`reference-image ${className}`}>
      {failed ? (
        <Placeholder label={alt} />
      ) : (
        <img src={src} alt={alt} onError={() => setFailed(true)} />
      )}
      <figcaption>{caption}</figcaption>
    </figure>
  );
}
