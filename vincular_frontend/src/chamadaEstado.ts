import type { ItemChamada, RegistroChamada, Situacao } from "./tipos.ts";

export interface Rascunho {
  situacao: Situacao | null;
  justificativa: string;
}

export type Rascunhos = Record<number, Rascunho>;

export interface Resumo {
  presentes: number;
  ausentes: number;
  justificadas: number;
  pendentes: number;
}

export function rascunhosIniciais(itens: ItemChamada[]): Rascunhos {
  const resultado: Rascunhos = {};
  for (const item of itens) {
    resultado[item.crianca] = { situacao: item.situacao, justificativa: item.justificativa ?? "" };
  }
  return resultado;
}

export function definirSituacao(rascunhos: Rascunhos, crianca: number, situacao: Situacao): Rascunhos {
  const atual = rascunhos[crianca] ?? { situacao: null, justificativa: "" };
  return { ...rascunhos, [crianca]: { ...atual, situacao } };
}

export function definirJustificativa(rascunhos: Rascunhos, crianca: number, texto: string): Rascunhos {
  const atual = rascunhos[crianca] ?? { situacao: null, justificativa: "" };
  return { ...rascunhos, [crianca]: { ...atual, justificativa: texto } };
}

/** Marca como presente só quem ainda não tem marcação; não mexe nas escolhas já feitas. */
export function marcarPendentesComoPresentes(rascunhos: Rascunhos): Rascunhos {
  const resultado: Rascunhos = {};
  for (const [id, rascunho] of Object.entries(rascunhos)) {
    resultado[Number(id)] =
      rascunho.situacao === null ? { ...rascunho, situacao: "presente" } : rascunho;
  }
  return resultado;
}

export function validarRascunhos(rascunhos: Rascunhos): string | null {
  const faltam = Object.values(rascunhos).filter(
    (r) => r.situacao === "ausente_justificada" && r.justificativa.trim() === "",
  ).length;
  if (faltam === 0) return null;
  return faltam === 1
    ? 'Escreva a justificativa da criança marcada como "Ausente justificada".'
    : `Escreva a justificativa das ${faltam} crianças marcadas como "Ausente justificada".`;
}

/** Só as crianças marcadas entram no envio; a justificativa só vai na ausência justificada. */
export function montarRegistros(rascunhos: Rascunhos): RegistroChamada[] {
  const registros: RegistroChamada[] = [];
  for (const [id, rascunho] of Object.entries(rascunhos)) {
    const situacao = rascunho.situacao;
    if (situacao === null) continue;
    if (situacao === "ausente_justificada") {
      registros.push({ crianca: Number(id), situacao, justificativa: rascunho.justificativa.trim() });
    } else {
      registros.push({ crianca: Number(id), situacao });
    }
  }
  return registros;
}

export function resumir(rascunhos: Rascunhos, total: number): Resumo {
  const resumo: Resumo = { presentes: 0, ausentes: 0, justificadas: 0, pendentes: 0 };
  let marcadas = 0;
  for (const rascunho of Object.values(rascunhos)) {
    if (rascunho.situacao === "presente") resumo.presentes += 1;
    else if (rascunho.situacao === "ausente") resumo.ausentes += 1;
    else if (rascunho.situacao === "ausente_justificada") resumo.justificadas += 1;
    if (rascunho.situacao !== null) marcadas += 1;
  }
  resumo.pendentes = Math.max(total - marcadas, 0);
  return resumo;
}

export function houveMudanca(rascunhos: Rascunhos, itens: ItemChamada[]): boolean {
  for (const item of itens) {
    const atual = rascunhos[item.crianca];
    const situacao = atual?.situacao ?? null;
    if (situacao !== item.situacao) return true;
    if (
      situacao === "ausente_justificada" &&
      (atual?.justificativa ?? "").trim() !== (item.justificativa ?? "").trim()
    ) {
      return true;
    }
  }
  return false;
}
