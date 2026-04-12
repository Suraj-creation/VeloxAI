export function classNames(...parts: Array<string | undefined | false>) {
  return parts.filter(Boolean).join(' ')
}
