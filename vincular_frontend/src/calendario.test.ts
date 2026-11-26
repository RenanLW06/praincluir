import assert from "node:assert/strict";
import { test } from "node:test";

import {
  dataValida, diaDaSemanaISO, formatarData, horarioDaTurma, nomeDoDia, somarDias, turmasDoDia,
} from "./calendario.ts";
import type { DiaTurma, Turma } from "./tipos.ts";

const DIAS: DiaTurma[] = [
  { letra: "A", dia_semana: 1 },
  { letra: "B", dia_semana: 2 },
  { letra: "C", dia_semana: 3 },
  { letra: "D", dia_semana: 4 },
  { letra: "E", dia_semana: 5 },
];

function turma(id: number, sala: string, letra: string, horario: "D1" | "D2", tempo: 1 | 2): Turma {
  return { id, sala: id, sala_nome: sala, letra, horario, tempo, capacidade: 6, ano: 2026 };
}

test("dia da semana: 07/12/2026 é segunda e 06/12/2026 é domingo", () => {
  assert.equal(diaDaSemanaISO("2026-12-07"), 1);
  assert.equal(diaDaSemanaISO("2026-12-06"), 7);
  assert.equal(nomeDoDia("2026-12-08"), "terça-feira");
});

test("somar dias atravessa mês e ano", () => {
  assert.equal(somarDias("2026-12-31", 1), "2027-01-01");
  assert.equal(somarDias("2026-03-01", -1), "2026-02-28");
});

test("formatar e validar datas", () => {
  assert.equal(formatarData("2026-12-07"), "07/12/2026");
  assert.equal(dataValida("2026-02-30"), false);
  assert.equal(dataValida("07/12/2026"), false);
  assert.equal(dataValida("2026-12-07"), true);
});

test("horários dos tempos de D1 e D2", () => {
  assert.equal(horarioDaTurma({ horario: "D1", tempo: 1 }), "13:30–14:30");
  assert.equal(horarioDaTurma({ horario: "D1", tempo: 2 }), "14:30–15:30");
  assert.equal(horarioDaTurma({ horario: "D2", tempo: 1 }), "15:30–16:30");
  assert.equal(horarioDaTurma({ horario: "D2", tempo: 2 }), "16:30–17:30");
});

test("turmas do dia: só as da letra daquele dia, em ordem de horário e tempo", () => {
  const turmas = [
    turma(1, "Sala Z", "A", "D2", 1),
    turma(2, "Sala Y", "A", "D1", 2),
    turma(3, "Sala X", "A", "D1", 1),
    turma(4, "Sala X", "B", "D1", 1),
  ];
  const segunda = turmasDoDia(turmas, DIAS, "2026-12-07");
  assert.deepEqual(segunda.map((t) => t.id), [3, 2, 1]);
  assert.deepEqual(turmasDoDia(turmas, DIAS, "2026-12-08").map((t) => t.id), [4]);
  assert.deepEqual(turmasDoDia(turmas, DIAS, "2026-12-06"), []); // domingo
  assert.deepEqual(turmasDoDia(turmas, DIAS, "data errada"), []);
});
