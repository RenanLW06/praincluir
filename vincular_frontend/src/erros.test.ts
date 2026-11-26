import assert from "node:assert/strict";
import { test } from "node:test";

import { mensagemDeErro } from "./erros.ts";

test("mensagem simples (detail)", () => {
  assert.equal(mensagemDeErro({ detail: "Turma lotada." }, "Erro"), "Turma lotada.");
});

test("erros por campo viram uma frase", () => {
  const corpo = { data: ["A turma A tem aula às segundas-feiras."], justificativa: ["Obrigatória."] };
  assert.equal(
    mensagemDeErro(corpo, "Erro"),
    "A turma A tem aula às segundas-feiras. Obrigatória.",
  );
});

test("erros aninhados e repetidos aparecem uma vez só", () => {
  const corpo = { registros: ["Criança 3 repetida.", "Criança 3 repetida."] };
  assert.equal(mensagemDeErro(corpo, "Erro"), "Criança 3 repetida.");
});

test("sem corpo, usa a mensagem padrão", () => {
  assert.equal(mensagemDeErro(null, "Erro 500"), "Erro 500");
  assert.equal(mensagemDeErro({}, "Erro 500"), "Erro 500");
});
