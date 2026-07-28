import { clsx } from "clsx";
import { extendTailwindMerge } from "tailwind-merge"

// Tailwind-merge doesn't know about the custom named font-size scale defined in
// index.css (--text-display-lg, --text-body, etc. — see the @theme block) since
// they're not part of its built-in class-group config. Without this, e.g.
// cn("text-sm", "text-heading") keeps BOTH classes instead of dropping text-sm,
// and which one wins becomes a coin flip based on generated CSS order rather
// than intent — that's what caused the query textarea's font-size (and, via the
// text-input/--color-input name collision, its color) to silently not apply.
const twMerge = extendTailwindMerge({
  extend: {
    classGroups: {
      "font-size": [
        { text: ["display-lg", "display-sm", "heading", "body", "caption", "label", "data", "prompt"] },
      ],
    },
  },
})

export function cn(...inputs) {
  return twMerge(clsx(inputs));
}
