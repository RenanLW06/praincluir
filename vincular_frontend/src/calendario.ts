import type { DiaTurma, Turma } from "./tipos.ts";

export const NOMES_DIAS: Record<number, string> = {
  1: "segunda-feira",
  2: "terça-feira",
  3: "quarta-feira",
  4: "quinta-feira",
  5: "sexta-feira",
  6: "sábado",
  7: "domingo",
};

// D1 e D2 não são dias da semana: são horários, cada um com dois tempos de 1h.
const HORARIOS: Record<string, string> = {
  "D1-1": "13:30–14:30",
  "D1-2": "14:30–15:30",
  "D2-1": "15:30–16:30",
  "D2-2": "16:30–17:30",
};

const FORMATO = /^(\d{4})-(\d{2})-(\d{2})$/;

function partes(dataISO: string): [number, number, number] {
  const m = FORMATO.exec(dataISO);
  if (!m) throw new Error(`Data inválida: ${dataISO}`);
  return [Number(m[1]), Number(m[2]), Number(m[3])];
}

function dois(n: number): string {
  return String(n).padStart(2, "0");
}

export function dataValida(dataISO: string): boolean {
  const m = FORMATO.exec(dataISO);
  if (!m) return false;
  const [a, mes, d] = [Number(m[1]), Number(m[2]), Number(m[3])];
  const data = new Date(a, mes - 1, d);
  return data.getFullYear() === a && data.getMonth() === mes - 1 && data.getDate() === d;
}

export function paraISO(data: Date): string {
  return `${data.getFullYear()}-${dois(data.getMonth() + 1)}-${dois(data.getDate())}`;
}

export function hojeISO(): string {
  return paraISO(new Date());
}

export function somarDias(dataISO: string, dias: number): string {
  const [a, m, d] = partes(dataISO);
  return paraISO(new Date(a, m - 1, d + dias));
}

/** Dia da semana no padrão ISO: 1 = segunda ... 7 = domingo. */
export function diaDaSemanaISO(dataISO: string): number {
  const [a, m, d] = partes(dataISO);
  const js = new Date(a, m - 1, d).getDay(); // 0 = domingo
  return js === 0 ? 7 : js;
}

export function nomeDoDia(dataISO: string): string {
  return NOMES_DIAS[diaDaSemanaISO(dataISO)] ?? "";
}

export function formatarData(dataISO: string): string {
  const [a, m, d] = partes(dataISO);
  return `${dois(d)}/${dois(m)}/${a}`;
}

export function horarioDaTurma(turma: Pick<Turma, "horario" | "tempo">): string {
  return HORARIOS[`${turma.horario}-${turma.tempo}`] ?? "";
}

export function rotuloTurma(turma: Turma): string {
  return `${turma.horario} · ${turma.tempo}º tempo (${horarioDaTurma(turma)}) · ${turma.sala_nome}`;
}

function comparar(a: Turma, b: Turma): number {
  return (
    a.horario.localeCompare(b.horario) ||
    a.tempo - b.tempo ||
    a.sala_nome.localeCompare(b.sala_nome, "pt-BR")
  );
}

/** Turmas que têm aula na data informada (a letra da turma é o dia da semana). */
export function turmasDoDia(turmas: Turma[], dias: DiaTurma[], dataISO: string): Turma[] {
  if (!dataValida(dataISO)) return [];
  const dia = diaDaSemanaISO(dataISO);
  const letras = new Set(dias.filter((d) => d.dia_semana === dia).map((d) => d.letra));
  return turmas.filter((t) => letras.has(t.letra)).sort(comparar);
}
