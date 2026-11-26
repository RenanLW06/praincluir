import assert from "node:assert/strict";
import { test } from "node:test";

import {
  definirJustificativa, definirSituacao, houveMudanca, marcarPendentesComoPresentes,
  montarRegistros, rascunhosIniciais, resumir, validarRascunhos,
} from "./chamadaEstado.ts";
import type { ItemChamada } from "./tipos.ts";

const ITENS: ItemChamada[] = [
  { crianca: 1, nome: "Crianca 1", codigo_v: "T001", realocada: false, situacao: null, justificativa: null },
  { crianca: 2, nome: "Crianca 2", codigo_v: "T002", realocada: false, situacao: "presente", justificativa: null },
  { crianca: 3, nome: "Crianca 3", codigo_v: "T003", realocada: true, situacao: null, justificativa: null },
];

test("rascunhos iniciais copiam o que já foi salvo", () => {
  const r = rascunhosIniciais(ITENS);
  assert.equal(r[2]?.situacao, "presente");
  assert.equal(r[1]?.situacao, null);
  assert.equal(houveMudanca(r, ITENS), false);
});

test("marcar pendentes como presentes não muda escolhas já feitas", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 1, "ausente");
  r = marcarPendentesComoPresentes(r);
  assert.equal(r[1]?.situacao, "ausente");
  assert.equal(r[2]?.situacao, "presente");
  assert.equal(r[3]?.situacao, "presente");
});

test("ausência justificada exige texto", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 1, "ausente_justificada");
  assert.match(validarRascunhos(r) ?? "", /justificativa/);
  r = definirJustificativa(r, 1, "   ");
  assert.notEqual(validarRascunhos(r), null);
  r = definirJustificativa(r, 1, "Consulta médica");
  assert.equal(validarRascunhos(r), null);
});

test("registros enviados: só marcados, justificativa só quando justificada", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 1, "ausente_justificada");
  r = definirJustificativa(r, 1, "  Consulta  ");
  const registros = montarRegistros(r);
  assert.deepEqual(registros, [
    { crianca: 1, situacao: "ausente_justificada", justificativa: "Consulta" },
    { crianca: 2, situacao: "presente" },
  ]);
});

test("trocar de ausente justificada para presente não envia justificativa", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 1, "ausente_justificada");
  r = definirJustificativa(r, 1, "Consulta");
  r = definirSituacao(r, 1, "presente");
  const primeiro = montarRegistros(r).find((x) => x.crianca === 1);
  assert.deepEqual(primeiro, { crianca: 1, situacao: "presente" });
});

test("resumo conta cada situação e os pendentes", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 1, "ausente");
  assert.deepEqual(resumir(r, 3), { presentes: 1, ausentes: 1, justificadas: 0, pendentes: 1 });
});

test("detecta alteração em relação ao salvo", () => {
  let r = rascunhosIniciais(ITENS);
  r = definirSituacao(r, 2, "ausente");
  assert.equal(houveMudanca(r, ITENS), true);
});
