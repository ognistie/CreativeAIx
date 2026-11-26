// Gerado por app/scripts/export_ui_contract.py. Nao edite a mao.
// Fonte: desktop/server.py (RPC_METHODS), desktop/bridge_core.py e tests/fixtures/bridge_contract.txt.

export const PROTOCOL_VERSION = 1;

/** Metodos do nucleo: nome -> [argumentos, retorno]. Mesmos nomes dos @Slots do Bridge. */
export interface Methods {
  activitySummary: [args: [], result: unknown];
  agentProfile: [args: [agent: string], result: unknown];
  appearance: [args: [], result: unknown];
  approvePlan: [args: [ok: boolean, token: string], result: null];
  approvePlanSteps: [args: [token: string, skipped_json: string], result: null];
  attachFiles: [args: [payload: string], result: unknown];
  brainCreate: [args: [rel: string, text: string], result: unknown];
  brainCreateFolder: [args: [rel: string], result: unknown];
  brainDelete: [args: [rel: string], result: unknown];
  brainGraph: [args: [], result: unknown];
  brainOverview: [args: [], result: unknown];
  brainRead: [args: [rel: string], result: unknown];
  brainRename: [args: [old: string, new: string], result: unknown];
  brainRestore: [args: [rel: string], result: unknown];
  brainSave: [args: [rel: string, text: string], result: unknown];
  brainSearch: [args: [query: string], result: unknown];
  closeMini: [args: [], result: null];
  codingAgentsCheck: [args: [], result: null];
  creatorApply: [args: [pid: string], result: unknown];
  creatorDiscard: [args: [pid: string], result: null];
  creatorPropose: [args: [text: string], result: null];
  deleteConversation: [args: [sid: string], result: boolean];
  devAct: [args: [pid: string, action: string], result: unknown];
  devCheck: [args: [pid: string], result: unknown];
  devDiff: [args: [pid: string], result: unknown];
  devList: [args: [], result: unknown];
  devPropose: [args: [request: string, tool: string], result: unknown];
  executeTask: [args: [task: string, dry_run: boolean, generate_report: boolean], result: null];
  forceStop: [args: [], result: null];
  getSettings: [args: [], result: unknown];
  harnessGet: [args: [], result: unknown];
  harnessPatch: [args: [payload: string, label: string], result: unknown];
  harnessRestore: [args: [version_id: string], result: unknown];
  harnessSave: [args: [payload: string, label: string], result: unknown];
  historyDetail: [args: [task_id: string], result: unknown];
  introSeen: [args: [], result: unknown];
  journalDates: [args: [], result: unknown];
  journalDelete: [args: [entry_id: string], result: unknown];
  journalFolders: [args: [], result: unknown];
  journalGet: [args: [entry_id: string], result: unknown];
  journalList: [args: [query: string, tag: string, day: string], result: unknown];
  journalListIn: [args: [folder: string, query: string, tag: string, day: string], result: unknown];
  journalSave: [args: [payload: string], result: unknown];
  journalSetPrivate: [args: [entry_id: string, private_: boolean], result: unknown];
  journalSummarize: [args: [entry_id: string], result: null];
  journalUseInBrain: [args: [on: boolean], result: unknown];
  labArchive: [args: [version_id: string, archived: boolean], result: unknown];
  labCancel: [args: [], result: null];
  labCreateVariant: [args: [payload: string], result: unknown];
  labDataset: [args: [payload: string], result: unknown];
  labDiff: [args: [a: string, b: string], result: unknown];
  labDraftRoute: [args: [payload: string], result: unknown];
  labEvalSets: [args: [], result: unknown];
  labFeedback: [args: [payload: string], result: unknown];
  labObserve: [args: [agent: string, state: string], result: unknown];
  labPromote: [args: [version_id: string], result: unknown];
  labPromotionCheck: [args: [version_id: string], result: unknown];
  labPublish: [args: [version_id: string], result: unknown];
  labReport: [args: [run_id: string, format: string, hypothesis: string], result: unknown];
  labResearch: [args: [payload: string], result: unknown];
  labRollback: [args: [agent: string, active: string, confirmed: boolean], result: unknown];
  labRun: [args: [payload: string], result: unknown];
  labRunDetail: [args: [run_id: string], result: unknown];
  labRuns: [args: [], result: unknown];
  labSkills: [args: [agent: string], result: unknown];
  labToolTest: [args: [name: string, args_json: string], result: unknown];
  labTraining: [args: [], result: unknown];
  labVersions: [args: [agent: string], result: unknown];
  libraryCatalog: [args: [query: string, level: string, kind: string], result: unknown];
  librarySearch: [args: [query: string, level: string, kind: string], result: unknown];
  libraryTopic: [args: [topic_id: string], result: unknown];
  loadConversations: [args: [include_turns: boolean], result: unknown];
  loadHistory: [args: [], result: unknown];
  mainActivated: [args: [], result: null];
  newSession: [args: [], result: null];
  openBrainFolder: [args: [], result: null];
  openConversation: [args: [sid: string], result: unknown];
  providerCustomRemove: [args: [name: string], result: unknown];
  providerCustomSave: [args: [payload: string], result: unknown];
  providerKeyRemove: [args: [name: string], result: unknown];
  providerKeySave: [args: [name: string, key: string], result: unknown];
  providerModels: [args: [name: string], result: unknown];
  providerStatus: [args: [], result: unknown];
  renameConversation: [args: [sid: string, title: string], result: boolean];
  restoreMain: [args: [], result: null];
  rsiDecide: [args: [candidate: string, decision: string, confirmed: boolean], result: unknown];
  rsiHistory: [args: [agent: string], result: unknown];
  saveSettings: [args: [payload: string], result: unknown];
  setIntroSeen: [args: [key: string, seen: boolean], result: null];
  setLiveConversation: [args: [on: boolean], result: null];
  setTitleBarColor: [args: [color: string], result: null];
  studioAgent: [args: [agent: string], result: unknown];
  studioSave: [args: [agent: string, payload: string], result: unknown];
  studioSource: [args: [agent: string, path: string], result: unknown];
  suggestionApprove: [args: [sid: string, title: string, body: string], result: unknown];
  suggestionDismiss: [args: [sid: string], result: unknown];
  suggestionsList: [args: [], result: unknown];
  uiSettings: [args: [], result: unknown];
  voiceRecordCancel: [args: [], result: null];
  voiceRecordToggle: [args: [], result: null];
  wallpaperImport: [args: [url: string], result: unknown];
  wallpaperInfo: [args: [wallpaper: string], result: unknown];
  wallpaperRemove: [args: [wallpaper: string], result: unknown];
  wallpapersList: [args: [], result: unknown];
  youProfile: [args: [], result: unknown];
  youSave: [args: [section: string, text: string], result: unknown];
  /** So no host Qt (desktop/web_host.py). */
  openExternal: [args: [url: string], result: boolean];
  /** So no host Qt (desktop/web_host.py). */
  pickFiles: [args: [], result: unknown];
  /** So no host Qt (desktop/web_host.py). */
  pickFolder: [args: [], result: unknown];
  /** So no host Qt (desktop/web_host.py). */
  saveLabFile: [args: [name: string, content: string], result: unknown];
  /** So no host Qt (desktop/web_host.py). */
  windowClose: [args: [], result: null];
  /** So no host Qt (desktop/web_host.py). */
  windowMinimize: [args: [], result: null];
  /** So no host Qt (desktop/web_host.py). */
  windowStartMove: [args: [], result: null];
  /** So no host Qt (desktop/web_host.py). */
  windowStartResize: [args: [edge: string], result: null];
  /** So no host Qt (desktop/web_host.py). */
  windowState: [args: [], result: unknown];
  /** So no host Qt (desktop/web_host.py). */
  windowToggleMaximize: [args: [], result: unknown];
}

export type MethodName = keyof Methods;

/** Eventos do nucleo: mesmos nomes dos Signals do Bridge. Payload JSON ja decodificado. */
export interface Events {
  answerDelta: unknown;
  answerReady: unknown;
  apiUsage: unknown;
  assistantMessage: unknown;
  cancelled: unknown;
  codingStatus: unknown;
  contextExtracted: unknown;
  conversationsChanged: unknown;
  creatorReady: unknown;
  devChanged: unknown;
  errorRaised: unknown;
  executionFinished: unknown;
  historyChanged: unknown;
  journalSummary: unknown;
  labFinished: unknown;
  labProgress: unknown;
  logEntry: unknown;
  phaseChanged: unknown;
  planReady: unknown;
  planReview: unknown;
  quickEntry: null;
  reportReady: unknown;
  resolved: unknown;
  runningChanged: boolean;
  sessionReset: unknown;
  stepDone: unknown;
  stepStart: unknown;
  taskDone: unknown;
  voiceChat: unknown;
  voiceCommand: unknown;
  voiceHeard: unknown;
  voiceLevel: unknown;
  voiceReply: unknown;
  voiceState: unknown;
}

export type EventName = keyof Events;
