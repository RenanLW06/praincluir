export type Perfil = "administrador" | "monitor";

export interface Usuario {
  id: number;
  nome: string;
  perfil: Perfil;
}

export interface Sessao {
  token: string;
  usuario: Usuario;
}

export interface DiaTurma {
  letra: string;
  dia_semana: number; // ISO: 1 = segunda ... 7 = domingo
}

export interface Turma {
  id: number;
  sala: number;
  sala_nome: string;
  letra: string;
  horario: "D1" | "D2";
  tempo: 1 | 2;
  capacidade: number;
  ano: number;
  ocupadas?: number;
}

export type Situacao = "presente" | "ausente" | "ausente_justificada";

export interface ItemChamada {
  crianca: number;
  nome: string;
  codigo_v: string;
  realocada: boolean;
  situacao: Situacao | null;
  justificativa: string | null;
}

export interface ChamadaDia {
  turma: number;
  sala: string;
  data: string; // AAAA-MM-DD
  capacidade: number;
  criancas: ItemChamada[];
}

export interface Pagina<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

export interface RegistroChamada {
  crianca: number;
  situacao: Situacao;
  justificativa?: string;
}
