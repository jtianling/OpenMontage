import { staticFile } from "remotion";

export function resolveAsset(src: string): string {
  if (
    !src ||
    /^[a-zA-Z][a-zA-Z0-9+.-]*:/.test(src) ||
    src.startsWith("/") ||
    src.includes("\\") ||
    src.split("/").includes("..")
  ) {
    throw new Error("Use a project-relative asset under public/.");
  }
  return staticFile(src);
}
