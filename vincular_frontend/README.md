# Vincular — Front-end

React + TypeScript + Tailwind CSS (Vite). Primeira versão: **login** e **tela de chamada** (monitor e administrador).

## Antes de começar

1. **Node.js LTS** (versão 22 ou mais nova): https://nodejs.org — confira com `node --version`.
2. **O backend precisa estar rodando** (banco no Docker + `python manage.py runserver` na porta 8000).

## Rodar

```powershell
cd C:\Users\usuario\iprede\vincular_frontend
npm install
npm run dev
```

Abra http://localhost:5173 no navegador. O Vite repassa `/api` para o Django em `localhost:8000`,
então não é preciso configurar CORS em desenvolvimento.

Se o PowerShell reclamar de "execução de scripts desabilitada" ao rodar o `npm`, use uma vez neste terminal:
`Set-ExecutionPolicy -Scope Process RemoteSigned`

## Como a tela de chamada funciona

- Escolha a **data**: a tela mostra só as turmas que têm aula nesse dia (A = segunda ... E = sexta).
  O monitor vê as turmas das suas salas; o administrador vê todas.
- Marque **Presente**, **Ausente** ou **Justificada** (com motivo obrigatório) para cada criança.
- **Salvar chamada** grava de uma vez. Quem ficou sem marcação não é enviado.
- Crianças realocadas para a turma naquele dia aparecem com a etiqueta **Realocada**.
- Trocar de data ou de turma com marcações não salvas pede confirmação.
- Se a sessão expirar, a tela volta ao login. A sessão fica no `sessionStorage` (some ao fechar a aba).

## Conferências

```powershell
npm test            # testes das regras da tela (datas, horários, rascunho da chamada, mensagens de erro)
npm run typecheck   # confere os tipos do TypeScript
npm run build       # gera a versão de produção em dist/
```

Para produção, defina `VITE_API_URL` (ex.: `https://api.exemplo.com/api`) antes do `npm run build`
e inclua o endereço do front em `DJANGO_CORS_ORIGINS` no backend.

## Estrutura

| Arquivo | Para que serve |
|---|---|
| `src/api.ts` | Chamadas à API, token e tratamento de erros |
| `src/AuthContext.tsx`, `src/Login.tsx` | Entrada e saída do sistema |
| `src/TelaChamada.tsx` | Tela de chamada |
| `src/calendario.ts` | Dias da semana, horários D1/D2 e turmas de cada dia |
| `src/chamadaEstado.ts` | Marcações em rascunho, validação e envio |
| `src/erros.ts` | Converte erros do backend em frases |
