import { initials } from "@/lib/scoring";

/**
 * El cuadradito de la empresa. No tenemos logos (y pedirlos a internet sería
 * un costo y una dependencia), así que van las iniciales. Es gris a propósito:
 * en esta app el color significa algo, y un color por empresa no significaría nada.
 */
export function Avatar({ name, size = "md" }: { name: string | null; size?: "sm" | "md" | "lg" }) {
  return (
    <span className={`avatar avatar-${size}`} aria-hidden="true">
      {initials(name)}
    </span>
  );
}
