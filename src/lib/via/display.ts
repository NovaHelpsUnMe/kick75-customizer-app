export function formatAssignmentLabel(value: string): string {
  if (!value) return "Unassigned";

  return value
    .replace(/^KC_/, "")
    .replace(/^QK_/, "")
    .replace(/_/g, " ")
    .replace(/\(([^)]+)\)/g, " $1")
    .trim();
}
