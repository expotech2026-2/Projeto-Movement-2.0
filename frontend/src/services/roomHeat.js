// Mesmas regras do firmware (maquinasLigadas em sketch.ino) e da API (room_volume em management.py).
export const LAB_SHARE = 0.8;
export const AREA_PER_PERSON_M2 = 1.5;
export const MIN_VOLUME_M3 = 20;

export function isLab(capacity, computers) {
  return computers > 0 && computers >= LAB_SHARE * capacity;
}

export function computersOn(people, computers, capacity) {
  if (people <= 0 || computers <= 0) return 0;
  const on = isLab(capacity, computers) ? people : Math.floor(people / 2);
  return Math.min(on, computers);
}

export function computerRule(capacity, computers) {
  if (!computers) return "Sem computadores: o alvo considera só as pessoas.";
  if (isLab(capacity, computers))
    return `Laboratório: um computador ligado por aluno, até os ${computers}.`;
  return `Um computador ligado a cada 2 alunos, até os ${computers}.`;
}

export function roomVolume(area, ceilingHeight, capacity) {
  const volume = (area || capacity * AREA_PER_PERSON_M2) * ceilingHeight;
  return Math.round(Math.max(volume, MIN_VOLUME_M3) * 10) / 10;
}
