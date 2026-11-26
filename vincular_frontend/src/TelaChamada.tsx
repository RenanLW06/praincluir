import { useEffect, useMemo, useRef, useState } from "react";

import { api, textoDoErro } from "./api.ts";
import {
  dataValida, formatarData, hojeISO, nomeDoDia, rotuloTurma, somarDias, turmasDoDia,
} from "./calendario.ts";
import {
  definirJustificativa, definirSituacao, houveMudanca, marcarPendentesComoPresentes,
  montarRegistros, rascunhosIniciais, resumir, validarRascunhos,
} from "./chamadaEstado.ts";
import type { Rascunhos } from "./chamadaEstado.ts";
import type { ChamadaDia, DiaTurma, ItemChamada, Situacao, Turma } from "./tipos.ts";

const OPCOES: { valor: Situacao; rotulo: string; ativo: string }[] = [
  { valor: "presente", rotulo: "Presente", ativo: "border-green-600 bg-green-600 text-white" },
  { valor: "ausente", rotulo: "Ausente", ativo: "border-red-600 bg-red-600 text-white" },
  {
    valor: "ausente_justificada",
    rotulo: "Justificada",
    ativo: "border-amber-500 bg-amber-500 text-white",
  },
];

const BOTAO_INATIVO = "border-slate-300 bg-white text-slate-700 hover:bg-slate-100";

interface LinhaProps {
  item: ItemChamada;
  situacao: Situacao | null;
  justificativa: string;
  desabilitado: boolean;
  aoEscolher: (situacao: Situacao) => void;
  aoJustificar: (texto: string) => void;
}

function LinhaCrianca({ item, situacao, justificativa, desabilitado, aoEscolher, aoJustificar }: LinhaProps) {
  return (
    <li className="space-y-3 px-4 py-3">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="font-medium text-slate-900">{item.nome}</p>
          <p className="text-xs text-slate-500">Código V: {item.codigo_v}</p>
        </div>
        {item.realocada && (
          <span className="rounded-full bg-purple-100 px-2 py-0.5 text-xs font-medium text-purple-700">
            Realocada
          </span>
        )}
      </div>

      <div className="grid grid-cols-3 gap-2" role="group" aria-label={`Situação de ${item.nome}`}>
        {OPCOES.map((opcao) => (
          <button
            key={opcao.valor}
            type="button"
            disabled={desabilitado}
            aria-pressed={situacao === opcao.valor}
            onClick={() => aoEscolher(opcao.valor)}
            className={`rounded-lg border px-2 py-2.5 text-sm font-semibold disabled:opacity-60 ${
              situacao === opcao.valor ? opcao.ativo : BOTAO_INATIVO
            }`}
          >
            {opcao.rotulo}
          </button>
        ))}
      </div>

      {situacao === "ausente_justificada" && (
        <textarea
          value={justificativa}
          onChange={(e) => aoJustificar(e.target.value)}
          disabled={desabilitado}
          rows={2}
          placeholder="Motivo da ausência (obrigatório)"
          aria-label={`Justificativa de ${item.nome}`}
          className="w-full rounded-lg border border-slate-300 px-3 py-2 text-sm focus:border-amber-500 focus:outline-none focus:ring-2 focus:ring-amber-200"
        />
      )}
    </li>
  );
}

export default function TelaChamada() {
  const [data, setData] = useState<string>(hojeISO());
  const [dias, setDias] = useState<DiaTurma[]>([]);
  const [turmas, setTurmas] = useState<Turma[]>([]);
  const [carregandoBase, setCarregandoBase] = useState(true);
  const [turmaId, setTurmaId] = useState<number | null>(null);
  const [chamada, setChamada] = useState<ChamadaDia | null>(null);
  const [rascunhos, setRascunhos] = useState<Rascunhos>({});
  const [carregando, setCarregando] = useState(false);
  const [salvando, setSalvando] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [aviso, setAviso] = useState<string | null>(null);
  const pedido = useRef(0);

  // Turmas e dias da semana: carregam uma vez.
  useEffect(() => {
    let cancelado = false;
    Promise.all([api.diasTurma(), api.turmas()])
      .then(([listaDias, listaTurmas]) => {
        if (cancelado) return;
        setDias(listaDias);
        setTurmas(listaTurmas);
      })
      .catch((e: unknown) => {
        if (!cancelado) setErro(textoDoErro(e));
      })
      .finally(() => {
        if (!cancelado) setCarregandoBase(false);
      });
    return () => {
      cancelado = true;
    };
  }, []);

  const turmasDia = useMemo(() => turmasDoDia(turmas, dias, data), [turmas, dias, data]);

  // Mantém uma turma válida selecionada para o dia escolhido.
  useEffect(() => {
    if (turmasDia.length === 0) {
      setTurmaId(null);
    } else if (turmaId === null || !turmasDia.some((t) => t.id === turmaId)) {
      setTurmaId(turmasDia[0].id);
    }
  }, [turmasDia, turmaId]);

  // Carrega a lista de chamada sempre que a turma ou a data mudam.
  useEffect(() => {
    if (turmaId === null) {
      pedido.current += 1;
      setChamada(null);
      setRascunhos({});
      return;
    }
    pedido.current += 1;
    const numero = pedido.current;
    setCarregando(true);
    setErro(null);
    setAviso(null);
    api
      .chamada(turmaId, data)
      .then((dados) => {
        if (numero !== pedido.current) return;
        setChamada(dados);
        setRascunhos(rascunhosIniciais(dados.criancas));
      })
      .catch((e: unknown) => {
        if (numero !== pedido.current) return;
        setChamada(null);
        setRascunhos({});
        setErro(textoDoErro(e));
      })
      .finally(() => {
        if (numero === pedido.current) setCarregando(false);
      });
  }, [turmaId, data]);

  const itens = chamada?.criancas ?? [];
  const alterado = chamada !== null && houveMudanca(rascunhos, itens);
  const resumo = resumir(rascunhos, itens.length);

  // Avisa antes de fechar a página com marcações não salvas.
  useEffect(() => {
    if (!alterado) return;
    const avisar = (evento: BeforeUnloadEvent) => evento.preventDefault();
    window.addEventListener("beforeunload", avisar);
    return () => window.removeEventListener("beforeunload", avisar);
  }, [alterado]);

  function confirmarDescarte(): boolean {
    return !alterado || window.confirm("Há marcações que não foram salvas. Deseja descartá-las?");
  }

  function trocarData(nova: string) {
    if (!dataValida(nova) || nova === data || !confirmarDescarte()) return;
    setData(nova);
  }

  function trocarTurma(id: number) {
    if (id === turmaId || !confirmarDescarte()) return;
    setTurmaId(id);
  }

  async function salvar() {
    if (!chamada || turmaId === null) return;
    const problema = validarRascunhos(rascunhos);
    if (problema) {
      setErro(problema);
      setAviso(null);
      return;
    }
    const registros = montarRegistros(rascunhos);
    if (registros.length === 0) {
      setErro("Marque pelo menos uma criança antes de salvar.");
      setAviso(null);
      return;
    }
    setSalvando(true);
    setErro(null);
    setAviso(null);
    try {
      const dados = await api.salvarChamada(turmaId, data, registros);
      pedido.current += 1; // descarta qualquer resposta antiga ainda a caminho
      setChamada(dados);
      setRascunhos(rascunhosIniciais(dados.criancas));
      const pendentes = dados.criancas.filter((c) => c.situacao === null).length;
      setAviso(
        pendentes === 0
          ? "Chamada salva."
          : `Chamada salva. ${pendentes} criança(s) ainda sem marcação.`,
      );
    } catch (e) {
      setErro(textoDoErro(e));
    } finally {
      setSalvando(false);
    }
  }

  const ocupado = carregando || salvando;

  return (
    <div className="space-y-4">
      <h1 className="text-2xl font-bold">Chamada</h1>

      <section className="space-y-3 rounded-2xl bg-white p-4 shadow-sm ring-1 ring-slate-200">
        <div>
          <label htmlFor="data-chamada" className="block text-sm font-medium text-slate-700">
            Data
          </label>
          <div className="mt-1 flex items-center gap-2">
            <button
              type="button"
              onClick={() => trocarData(somarDias(data, -1))}
              aria-label="Dia anterior"
              className="rounded-lg border border-slate-300 px-3 py-2 text-lg hover:bg-slate-100"
            >
              ‹
            </button>
            <input
              id="data-chamada"
              type="date"
              value={data}
              onChange={(e) => trocarData(e.target.value)}
              className="min-w-0 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-base focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-200"
            />
            <button
              type="button"
              onClick={() => trocarData(somarDias(data, 1))}
              aria-label="Dia seguinte"
              className="rounded-lg border border-slate-300 px-3 py-2 text-lg hover:bg-slate-100"
            >
              ›
            </button>
            <button
              type="button"
              onClick={() => trocarData(hojeISO())}
              className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-medium hover:bg-slate-100"
            >
              Hoje
            </button>
          </div>
          {dataValida(data) && (
            <p className="mt-1 text-sm capitalize text-slate-500">
              {nomeDoDia(data)}, {formatarData(data)}
            </p>
          )}
        </div>

        {turmasDia.length > 0 && (
          <div>
            <label htmlFor="turma-chamada" className="block text-sm font-medium text-slate-700">
              Turma
            </label>
            <select
              id="turma-chamada"
              value={turmaId ?? ""}
              onChange={(e) => trocarTurma(Number(e.target.value))}
              className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-base focus:border-blue-600 focus:outline-none focus:ring-2 focus:ring-blue-200"
            >
              {turmasDia.map((t) => (
                <option key={t.id} value={t.id}>
                  {rotuloTurma(t)}
                </option>
              ))}
            </select>
          </div>
        )}
      </section>

      {carregandoBase && <p className="text-sm text-slate-500">Carregando turmas...</p>}

      {!carregandoBase && turmasDia.length === 0 && (
        <p className="rounded-xl bg-white px-4 py-6 text-center text-slate-600 shadow-sm ring-1 ring-slate-200">
          Nenhuma turma sua tem aula neste dia. Escolha outra data.
        </p>
      )}

      {erro && (
        <p role="alert" className="rounded-xl bg-red-50 px-4 py-3 text-sm text-red-700 ring-1 ring-red-200">
          {erro}
        </p>
      )}
      {aviso && (
        <p role="status" className="rounded-xl bg-green-50 px-4 py-3 text-sm text-green-800 ring-1 ring-green-200">
          {aviso}
        </p>
      )}

      {chamada && (
        <section className="overflow-hidden rounded-2xl bg-white shadow-sm ring-1 ring-slate-200">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-200 px-4 py-3">
            <p className="text-sm text-slate-600">
              <strong className="text-green-700">{resumo.presentes}</strong> presentes ·{" "}
              <strong className="text-red-700">{resumo.ausentes}</strong> ausentes ·{" "}
              <strong className="text-amber-600">{resumo.justificadas}</strong> justificadas ·{" "}
              <strong>{resumo.pendentes}</strong> sem marcação
            </p>
            <button
              type="button"
              disabled={ocupado || resumo.pendentes === 0}
              onClick={() => setRascunhos(marcarPendentesComoPresentes(rascunhos))}
              className="rounded-lg border border-slate-300 px-3 py-1.5 text-sm font-medium text-slate-700 hover:bg-slate-100 disabled:opacity-50"
            >
              Marcar o restante como presente
            </button>
          </div>

          {itens.length === 0 ? (
            <p className="px-4 py-6 text-center text-slate-600">Nenhuma criança nesta turma neste dia.</p>
          ) : (
            <ul className="divide-y divide-slate-100">
              {itens.map((item) => (
                <LinhaCrianca
                  key={item.crianca}
                  item={item}
                  situacao={rascunhos[item.crianca]?.situacao ?? null}
                  justificativa={rascunhos[item.crianca]?.justificativa ?? ""}
                  desabilitado={ocupado}
                  aoEscolher={(situacao) => setRascunhos(definirSituacao(rascunhos, item.crianca, situacao))}
                  aoJustificar={(texto) => setRascunhos(definirJustificativa(rascunhos, item.crianca, texto))}
                />
              ))}
            </ul>
          )}
        </section>
      )}

      {chamada && itens.length > 0 && (
        <div className="sticky bottom-0 -mx-4 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
          <button
            type="button"
            onClick={() => void salvar()}
            disabled={ocupado || !alterado}
            className="w-full rounded-lg bg-blue-600 px-4 py-3 text-base font-semibold text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {salvando ? "Salvando..." : alterado ? "Salvar chamada" : "Nada para salvar"}
          </button>
        </div>
      )}

      {carregando && !chamada && <p className="text-sm text-slate-500">Carregando chamada...</p>}
    </div>
  );
}
