// ==========================================================================
// Arquivo Unificado de Scripts do Projeto Kyly MES (Dashboard + Coletor)
// Arquitetura: Offline-First, PWA, AJAX (Latência < 200ms) + Leitura Híbrida (Câmera, Laser e Manual)
// ==========================================================================

(function () {
    "use strict";

    // ==========================================================================
    // DADOS REAIS - Dashboard (Sem Mock Data)
    // ==========================================================================
    let OPERATORS_DATA = [];
    let EXCEPTIONS_DATA = [];

    // INICIALIZAÇÃO PRINCIPAL
    document.addEventListener("DOMContentLoaded", function () {
        setupThemeToggle();
        setupKeyboardNav();
        atualizarData();
        setupImportacao();

        // Se estiver no Painel de Operações, carrega os dados
        if (window.location.pathname.includes('/painel-operacoes')) {
            setupPainelOperacoes();
            setInterval(carregarEquipeTempoReal, 5000); // Poll a cada 5s
        }

        // Se estiver no Dashboard ADM
        if (window.location.pathname.includes('/dashboard') && !window.location.pathname.includes('/painel')) {
            if (typeof calcularBarrasGrafico === "function") calcularBarrasGrafico();
            setInterval(atualizarDashboardKpisGlobal, 5000); // Atualiza os blocos
        }

        // Habilita as leituras em todas as telas
        setupEntradasHibridas();

        // Injeta automaticamente o ícone de WiFi no cabeçalho
        const header = document.querySelector('header');
        if (header && !document.getElementById('wifi-status')) {
            const wifiSpan = document.createElement('span');
            wifiSpan.id = 'wifi-status';
            wifiSpan.style.cssText = "position: absolute; right: 15px; top: 15px; font-size: 20px;";
            wifiSpan.innerHTML = navigator.onLine ? "📶" : "📵";
            if (!window.location.pathname.includes('painel')) {
                header.style.position = 'relative'; // garante que o absolute funciona
                header.appendChild(wifiSpan);
            }

            window.addEventListener('online', () => wifiSpan.innerHTML = "📶");
            window.addEventListener('offline', () => wifiSpan.innerHTML = "📵");
        }

        // Carrega dados reais do banco ao entrar na tela de picking
        if (document.getElementById('codigoPeca') || document.getElementById('codigoEndereco')) {
            carregarDadosPicking();
            if (document.getElementById('reader')) {
                setTimeout(() => {
                    if (typeof window.iniciarScannerCamera === "function") {
                        window.iniciarScannerCamera('codigoPeca');
                    }
                }, 1000); // Aguarda a DOM e animações
            }
        }
    });

    // ──────────────────────────────────────────────────────────────────
    // FUNÇÕES DE COMUNICAÇÃO REAL COM O BANCO
    // ──────────────────────────────────────────────────────────────────

    async function atualizarDashboardKpisGlobal() {
        try {
            const res = await fetch('/api/kpis/dados/');
            if (!res.ok) return;
            const data = await res.json();

            // Atualiza KPIs do Dashboard Principal (index.html)
            const pphDb = document.getElementById('pph');
            const tempoMedioDb = document.getElementById('tempoMedio');
            const streakDb = document.getElementById('streak');
            const taxaAcertosDb = document.getElementById('taxaAcertos');
            const caixasHojeDb = document.getElementById('caixasHoje');
            const errosDb = document.getElementById('erros');
            const pecasPickadasDb = document.getElementById('pecasPickadas');

            if (pphDb) pphDb.innerText = data.pph_global;
            if (tempoMedioDb) tempoMedioDb.innerText = data.tempo_medio;
            if (streakDb) streakDb.innerText = data.streak;
            if (taxaAcertosDb) taxaAcertosDb.innerText = data.taxa_acerto + '%';
            if (caixasHojeDb) caixasHojeDb.innerText = data.caixas_finalizadas;
            if (errosDb) errosDb.innerText = data.total_erros;
            if (pecasPickadasDb) pecasPickadasDb.innerText = data.total_pecas_bipadas;

            // Se existir o layout simplificado (.kpi-card) de outra página
            const pphEl = document.querySelector('.kpi-card:nth-child(1) h2');
            const errosEl = document.querySelector('.kpi-card:nth-child(2) h2');
            const acertosEl = document.querySelector('.kpi-card:nth-child(3) h2');
            const opAtivosEl = document.querySelector('.kpi-card:nth-child(4) h2');

            if (pphEl) pphEl.innerText = data.pph_global;
            if (errosEl) errosEl.innerText = data.total_erros;
            if (acertosEl) acertosEl.innerText = data.taxa_acerto + '%';
            if (opAtivosEl) opAtivosEl.innerText = data.operadores_count;
        } catch (e) {
            console.error("Erro ao atualizar KPIs globais", e);
        }
    }

    async function carregarEquipeTempoReal() {
        try {
            const res = await fetch('/api/supervisor/equipe/');
            if (!res.ok) return;
            const data = await res.json();

            // Converte o formato do backend para o formato que a UI de cards espera
            OPERATORS_DATA = data.equipe.map(u => ({
                id: u.cracha,
                name: u.nome,
                location: u.setor || 'N/D',
                status: u.dispositivo_status === 'ONLINE' ? 'online' : (u.dispositivo_status === 'TIMEOUT' ? 'idle' : 'error'),
                pph: u.pph || 0,
                caixa: u.caixa || '-',
                sinal: u.dispositivo_status === 'ONLINE' ? 'agora' : (u.dispositivo_status === 'TIMEOUT' ? '> 5m' : 'Offline'),
                details: { matricula: u.cracha, setor: u.setor, tempoOnline: "-", ultimasCaixas: [], excecoes: 0, acuracia: "-", producaoDia: "-" }
            }));

            if (typeof renderOperators === "function") renderOperators();
        } catch (e) {
            console.error("Erro ao atualizar painel operações", e);
        }
    }

    // ==========================================================================
    // 1. LEITURA HÍBRIDA (Câmera Real + Laser Datalogic + Digitação Manual)
    // ==========================================================================
    let html5QrcodeScanner = null;
    let contextoScanAtual = null; // Armazena qual campo estamos lendo (ex: codigoSupervisor)

    /**
     * Função chamada para escanear peças via câmera continuamente
     * @param {string} inputId - O ID do campo que receberá o valor lido
     */
    window.iniciarScannerCamera = function (inputId) {
        contextoScanAtual = inputId;

        // Verifica se a div reader existe na tela atual
        if (!document.getElementById("reader")) return;

        // Modal legado (para as outras telas que não foram convertidas para câmera inline)
        const modal = document.getElementById('scanner-modal');
        if (modal) modal.style.display = 'flex';

        // Configura o Scanner nativo
        if (typeof Html5QrcodeScanner === 'undefined') {
            console.warn('Biblioteca de câmera não carregada.');
            return;
        }

        if (!html5QrcodeScanner) {
            html5QrcodeScanner = new Html5QrcodeScanner(
                "reader",
                { fps: 10, qrbox: { width: 250, height: 250 } },
                false
            );
            html5QrcodeScanner.render(onScanSuccess, onScanFailure);
        }
    };

    // Callback de Sucesso da Câmera
    function onScanSuccess(decodedText, decodedResult) {
        if (navigator.vibrate) navigator.vibrate(100);

        if (contextoScanAtual) {
            const input = document.getElementById(contextoScanAtual);
            if (input) {
                input.value = decodedText;

                // Simula o "Enter" na função correspondente ao campo ativo
                if (contextoScanAtual === 'codigoSupervisor') verificarSupervisor();
                else if (contextoScanAtual === 'codigoColaborador') verificarColaborador();
                else if (contextoScanAtual === 'codigoPapeleta') verificarPapeleta();
                else if (contextoScanAtual === 'codigoEndereco' || contextoScanAtual === 'codigoPeca') verificarEndereco();
            }
        }

        // Se estamos no modal legado, fechamos. Se estamos no picking inline, NÃO fechamos a câmera.
        if (document.getElementById('scanner-modal')) {
            fecharScannerCamera();
        } else {
            // Em modo inline (sempre ativo), focamos novamente no campo para a proxima peça
            setTimeout(() => {
                const input = document.getElementById(contextoScanAtual);
                if (input) input.focus();
            }, 500);
        }
    }

    function onScanFailure(error) {
        // Ignorado intencionalmente.
    }

    // CORREÇÃO: nome da função alinhado com o que os botões HTML chamam
    window.fecharScannerCamera = function () {
        if (html5QrcodeScanner) {
            html5QrcodeScanner.clear().catch(error => console.error("Erro ao limpar scanner", error));
            html5QrcodeScanner = null;
        }
        const modal = document.getElementById('scanner-modal');
        if (modal) modal.style.display = 'none';
    };

    // Alias para compatibilidade
    window.fecharScanner = window.fecharScannerCamera;

    /**
     * Habilita a tecla ENTER para todos os inputs, suportando o Laser físico 
     * e a digitação manual do operador.
     */
    function setupEntradasHibridas() {
        const inputsDeLeitura = ['codigoSupervisor', 'codigoColaborador', 'codigoPapeleta', 'codigoEndereco', 'codigoPeca'];

        inputsDeLeitura.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                // Foco automático para o laser já chegar lendo
                input.focus();

                // Se apertar Enter (o que o Laser do Datalogic faz automaticamente no final do bip)
                input.addEventListener('keydown', function (e) {
                    if (e.key === 'Enter') {
                        e.preventDefault(); // Evita recarregar a tela (submit form)
                        if (id === 'codigoSupervisor') verificarSupervisor();
                        else if (id === 'codigoColaborador') verificarColaborador();
                        else if (id === 'codigoPapeleta') verificarPapeleta();
                        else if (id === 'codigoEndereco') verificarEndereco();
                        else if (id === 'codigoPeca') verificarEndereco();
                    }
                });
            }
        });
    }

    // ==========================================================================
    // 2. FUNÇÕES DE VALIDAÇÃO (Regras de Negócio e Avanço de Telas)
    // ==========================================================================

    window.verificarSupervisor = async function () {
        const input = document.getElementById("codigoSupervisor");
        if (!input) return;
        const codigo = input.value.trim();

        if (codigo === "") {
            alert("Por favor, bip ou digite o código do supervisor.");
            return;
        }

        atualizarStatusComunicacao('processando', 'Validando Supervisor...');

        try {
            const resposta = await fetch('/auth/api/v1/validar-cracha/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ cracha: codigo, perfil: 'SUPERVISOR' })
            });
            const dados = await resposta.json();

            if (resposta.ok && dados.status === 'sucesso') {
                acionarFeedbackSensorial('success');
                atualizarStatusComunicacao('processando', `Bem-vindo, ${dados.nome}!`);
                setTimeout(() => { window.location.href = "/coletor/operador/"; }, 500);
            } else {
                acionarFeedbackSensorial('error');
                atualizarStatusComunicacao('off', 'Acesso negado.');
                alert(dados.mensagem || 'Acesso negado.');
                input.value = '';
                input.focus();
            }
        } catch (err) {
            console.error('Erro ao validar supervisor:', err);
            atualizarStatusComunicacao('off', 'Erro de comunicação.');
            alert('Erro ao conectar com o servidor.');
        }
    };

    window.verificarColaborador = async function () {
        const input = document.getElementById("codigoColaborador");
        if (!input) return;
        const codigo = input.value.trim();

        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Validando Operador...');

        try {
            const resposta = await fetch('/auth/api/v1/validar-cracha/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ cracha: codigo, perfil: 'COLABORADOR' })
            });
            const dados = await resposta.json();

            if (resposta.ok && dados.status === 'sucesso') {
                acionarFeedbackSensorial('success');
                atualizarStatusComunicacao('processando', `Operador: ${dados.nome}`);
                setTimeout(() => { window.location.href = "/coletor/abertura/"; }, 500);
            } else {
                acionarFeedbackSensorial('error');
                atualizarStatusComunicacao('off', 'Acesso negado.');
                alert(dados.mensagem || 'Operador não cadastrado ou sem turno ativo.');
                input.value = '';
                input.focus();
            }
        } catch (err) {
            console.error('Erro ao validar colaborador:', err);
            atualizarStatusComunicacao('off', 'Erro de comunicação.');
            alert('Erro ao conectar com o servidor.');
        }
    };

    window.verificarPapeleta = async function () {
        const input = document.getElementById("codigoPapeleta");
        if (!input) return;
        const codigo = input.value.trim();

        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Iniciando Sessão...');

        try {
            const resposta = await fetch('/api/picking/iniciar/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ numero_pedido: codigo })
            });
            const dados = await resposta.json();

            if (resposta.ok && dados.status === 'sucesso') {
                acionarFeedbackSensorial('success');
                atualizarStatusComunicacao('processando', `Pedido ${dados.pedido.numero} carregado!`);

                // Preenche os dados reais vindos do MySQL
                const elCliente = document.getElementById('cliente-nome');
                const elPedido = document.getElementById('pedido-numero');
                const elTotal = document.getElementById('pedido-total');
                const elPeso = document.getElementById('pedido-peso');
                const elDados = document.getElementById('dados-pedido');
                const btnIniciar = document.getElementById('btn-iniciar');
                const btnCamera = document.getElementById('btn-camera');

                if (elCliente) elCliente.textContent = dados.pedido.cliente;
                if (elPedido) elPedido.textContent = dados.pedido.numero;
                if (elTotal) elTotal.textContent = dados.pedido.total_pecas + " UN";
                if (elPeso) elPeso.textContent = parseFloat(dados.pedido.peso_bruto).toFixed(3) + "kg";

                // Exibe os blocos
                if (elDados) elDados.style.display = 'block';
                if (btnIniciar) {
                    btnIniciar.style.display = 'flex';
                    btnIniciar.focus(); // joga o foco pro botao pro cara dar enter
                }

                // Esconde a API de câmera e o input
                if (btnCamera) btnCamera.style.display = 'none';
                if (input) {
                    input.style.display = 'none';
                }

            } else {
                acionarFeedbackSensorial('error');
                atualizarStatusComunicacao('off', 'Erro ao abrir caixa.');
                alert(dados.mensagem || 'Pedido não encontrado ou já finalizado.');
                input.value = '';
                input.focus();
            }
        } catch (err) {
            console.error('Erro ao iniciar picking:', err);
            atualizarStatusComunicacao('off', 'Erro de comunicação.');
            alert('Erro ao conectar com o servidor.');
        }
    };

    // ==========================================================================
    // 2.A OFFLINE FIRST (INDEXED DB) E BACKGROUND SYNC
    // ==========================================================================
    let dbOffline;
    function initIndexedDB() {
        return new Promise((resolve, reject) => {
            const req = indexedDB.open('MESPickingDB', 1);
            req.onupgradeneeded = e => {
                const db = e.target.result;
                if (!db.objectStoreNames.contains('fila_bips')) {
                    db.createObjectStore('fila_bips', { keyPath: 'id', autoIncrement: true });
                }
            };
            req.onsuccess = e => { dbOffline = e.target.result; atualizarContadorOffline(); resolve(dbOffline); };
            req.onerror = e => reject(e.target.error);
        });
    }

    function atualizarContadorOffline() {
        if (!dbOffline) return;
        const tx = dbOffline.transaction('fila_bips', 'readonly');
        const req = tx.objectStore('fila_bips').count();
        req.onsuccess = () => {
            const wifiSpan = document.getElementById('wifi-status');
            if (wifiSpan) {
                if (req.result > 0) {
                    wifiSpan.innerHTML = `<span style="color:#f59e0b;font-weight:bold;font-size:14px;background:rgba(245,158,11,0.2);padding:2px 8px;border-radius:10px;margin-right:5px;">${req.result} ⏳</span> ` + (navigator.onLine ? "📶" : "📵");
                } else {
                    wifiSpan.innerHTML = navigator.onLine ? "📶" : "📵";
                }
            }
        };
    }

    async function salvarBipOffline(payload) {
        if (!dbOffline) await initIndexedDB();
        return new Promise((resolve, reject) => {
            const tx = dbOffline.transaction('fila_bips', 'readwrite');
            const store = tx.objectStore('fila_bips');
            store.add({ ...payload, timestamp: Date.now() });
            tx.oncomplete = () => { atualizarContadorOffline(); resolve(); };
            tx.onerror = e => reject(e.target.error);
        });
    }

    async function sincronizarBipsOffline() {
        if (!dbOffline) await initIndexedDB();
        if (!navigator.onLine) return;

        return new Promise((resolve, reject) => {
            const tx = dbOffline.transaction('fila_bips', 'readonly');
            const store = tx.objectStore('fila_bips');
            const req = store.getAll();
            req.onsuccess = async () => {
                const fila = req.result;
                if (fila.length === 0) return resolve();

                atualizarStatusComunicacao('processando', `Sincronizando ${fila.length} itens offline...`);
                let sucessoSync = 0;

                for (const item of fila) {
                    try {
                        const res = await fetch('/api/picking/validar-bip/', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                            body: JSON.stringify({ codigo: item.codigo, sessao_id: item.sessao_id, offline_sync: true })
                        });
                        if (res.ok) {
                            const txDel = dbOffline.transaction('fila_bips', 'readwrite');
                            txDel.objectStore('fila_bips').delete(item.id);
                            sucessoSync++;
                        }
                    } catch (err) { console.error("Erro no sync do item", item, err); }
                }

                atualizarContadorOffline();

                if (sucessoSync > 0) {
                    atualizarStatusComunicacao('off', `${sucessoSync} bipes sincronizados!`);
                    setTimeout(() => window.location.reload(), 1500); // Recarrega para pegar o estado real
                }
                resolve();
            };
        });
    }

    // Tenta sincronizar ao voltar a internet
    window.addEventListener('online', () => {
        atualizarContadorOffline();
        sincronizarBipsOffline();
    });
    window.addEventListener('offline', atualizarContadorOffline);
    // Tenta sincronizar ao carregar a página
    document.addEventListener('DOMContentLoaded', () => {
        initIndexedDB().then(() => { if (navigator.onLine) sincronizarBipsOffline(); });
    });


    // O Fluxo Principal de Picking da Peça - chama a API real do Django
    window.verificarEndereco = async function () {
        const input = document.getElementById("codigoPeca") || document.getElementById("codigoEndereco");
        if (!input) return;
        const codigo = input.value.trim();
        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Processando SKU...');
        const sessaoId = obterSessaoId();

        // MODO OFFLINE (Sem Internet)
        if (!navigator.onLine) {
            try {
                await salvarBipOffline({ codigo, sessao_id: sessaoId });
                // Efeito Flash Amarelo e Bipe pendente
                const body = document.body;
                body.classList.remove('flash-success', 'flash-error');
                void body.offsetWidth;
                body.style.animation = "flash-yellow 0.4s ease";
                setTimeout(() => body.style.animation = "", 400);

                atualizarStatusComunicacao('off', 'Salvo Offline (Na Fila)');

                // Em modo offline, avançamos visualmente o contador para não travar o operador
                const p = window.atualizarProgresso();
                if (p.atual >= p.total) {
                    setTimeout(() => { window.location.href = '/coletor/finalizar/'; }, 1000);
                } else {
                    input.value = '';
                    setTimeout(() => input.focus(), 100);
                }
            } catch (err) {
                alert("Falha ao salvar no banco local!");
            }
            return;
        }

        // MODO ONLINE (Normal)
        try {
            const resposta = await fetch('/api/picking/validar-bip/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ codigo: codigo, sessao_id: sessaoId })
            });
            const dados = await resposta.json();

            input.value = '';

            if (dados.status === 'finalizado') {
                acionarFeedbackSensorial('success');
                setTimeout(() => { window.location.href = '/coletor/finalizar/'; }, 400);
                return;
            }

            if (resposta.ok && dados.status === 'sucesso') {
                acionarFeedbackSensorial('success');
                atualizarStatusComunicacao('off', 'Peça validada! Próxima...');

                if (dados.kpis) window.atualizarDashboardKPIs(dados.kpis);
                if (dados.proximo_item) atualizarTelaPicking(dados.proximo_item, dados.progresso);

                if (input) setTimeout(() => input.focus(), 100);
            } else {
                acionarFeedbackSensorial('error');
                atualizarStatusComunicacao('off', dados.mensagem || 'Erro de bipagem.');
                if (window.mostrarModalErro) window.mostrarModalErro(codigo);
                if (input) { input.value = ''; input.focus(); }
            }
        } catch (err) {
            console.error('Erro ao validar bip:', err);
            // Se falhou a rede no meio do fetch, tenta salvar offline
            await salvarBipOffline({ codigo, sessao_id: sessaoId });
            atualizarStatusComunicacao('off', 'Erro rede. Salvo Offline.');
            input.value = '';
            setTimeout(() => input.focus(), 100);
        }
    };

    // Pular SKU - chama a API real
    window.pularSKU = async function () {
        atualizarStatusComunicacao('processando', 'Pulando item...');
        try {
            const resposta = await fetch('/api/picking/pular-sku/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ sessao_id: obterSessaoId() })
            });
            const dados = await resposta.json();
            if (dados.proximo_item) {
                atualizarTelaPicking(dados.proximo_item, dados.progresso);
                if (dados.kpis) window.atualizarDashboardKPIs(dados.kpis);
                atualizarStatusComunicacao('off', 'Item pulado. Próximo!');
            } else {
                window.location.href = '/coletor/finalizar/';
            }
        } catch (err) {
            console.error('Erro ao pular SKU:', err);
            atualizarStatusComunicacao('off', 'Erro de conexão.');
        }
    };

    // Peça danificada - chama a API real
    window.reportarDanificada = async function () {
        atualizarStatusComunicacao('processando', 'Registrando peça danificada...');
        try {
            const resposta = await fetch('/api/picking/danificada/', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCookie('csrftoken') },
                body: JSON.stringify({ sessao_id: obterSessaoId() })
            });
            const dados = await resposta.json();
            if (dados.proximo_item) {
                atualizarTelaPicking(dados.proximo_item, dados.progresso);
                if (dados.kpis) window.atualizarDashboardKPIs(dados.kpis);
                atualizarStatusComunicacao('off', 'Peça marcada como danificada.');
            } else {
                window.location.href = '/coletor/finalizar/';
            }
        } catch (err) {
            console.error('Erro ao reportar danificada:', err);
        }
    };

    // Carrega os dados reais da sessão ao entrar na tela de picking
    window.carregarDadosPicking = async function () {
        try {
            const resposta = await fetch('/api/picking/status/', {
                headers: { 'X-CSRFToken': getCookie('csrftoken') }
            });
            if (!resposta.ok) return; // sem sessão
            const dados = await resposta.json();

            window._sessaoId = dados.sessao_id;

            if (dados.pedido) {
                const prog = document.querySelector('.header-progress');
                if (prog) prog.textContent = `${dados.pedido.pecas_bipadas}/${dados.pedido.total_pecas}`;
                const pct = dados.pedido.total_pecas > 0
                    ? (dados.pedido.pecas_bipadas / dados.pedido.total_pecas) * 100 : 0;
                const barra = document.querySelector('.barra-fill');
                if (barra) barra.style.width = pct + '%';
                const errosEl = document.querySelector('[data-erros]');
                if (errosEl) errosEl.textContent = dados.erros || 0;
            }
            if (dados.kpis) window.atualizarDashboardKPIs(dados.kpis);
            if (dados.item_atual) atualizarTelaPicking(dados.item_atual, null);
        } catch (err) {
            console.warn('Não foi possível carregar sessão:', err);
        }
    };

    let timerInterval = null;

    window.atualizarDashboardKPIs = function (kpis) {
        if (!kpis) return;
        const pphEl = document.querySelector('[data-pph]');
        const tempoEl = document.querySelector('[data-tempo]');
        const streakEl = document.querySelector('[data-streak]');
        const errosEl = document.querySelector('[data-erros]');

        if (pphEl) pphEl.textContent = kpis.pph;
        if (tempoEl) tempoEl.textContent = kpis.tempo;
        if (streakEl) streakEl.textContent = kpis.streak;
        if (errosEl) errosEl.textContent = kpis.erros;

        // Inicia ou reinicia o cronômetro para bater os segundos localmente na tela
        if (timerInterval) clearInterval(timerInterval);
        if (tempoEl) {
            timerInterval = setInterval(() => {
                let partes = tempoEl.textContent.split(':');
                if (partes.length === 2) {
                    let m = parseInt(partes[0], 10);
                    let s = parseInt(partes[1], 10);
                    s++;
                    if (s >= 60) { s = 0; m++; }
                    tempoEl.textContent = (m < 10 ? "0" + m : m) + ":" + (s < 10 ? "0" + s : s);
                }
            }, 1000);
        }
    };

    // Atualiza os campos visuais com o próximo item do banco
    function atualizarTelaPicking(item, progresso) {
        const endEl = document.getElementById('enderecoAtual');
        if (endEl) endEl.textContent = item.endereco;

        const refEl = document.getElementById('peca-ref');
        const corEl = document.getElementById('peca-cor');
        const tamEl = document.getElementById('peca-tam');

        if (refEl) refEl.textContent = item.referencia;
        if (corEl) corEl.textContent = item.cor;
        if (tamEl) tamEl.textContent = item.tamanho;

        if (progresso) {
            const prog = document.querySelector('.header-progress');
            if (prog) prog.textContent = `${progresso.atual}/${progresso.total}`;
            const barra = document.querySelector('.barra-fill');
            const pct = progresso.total > 0 ? (progresso.atual / progresso.total) * 100 : 0;
            if (barra) barra.style.width = pct + '%';
        }
    }

    function obterSessaoId() {
        return window._sessaoId || null;
    }


    // ==========================================================================
    // 3. EFEITOS SENSORIAIS E UTILITÁRIOS (UI/UX Industrial)
    // ==========================================================================

    // Pré-carrega os elementos de áudio uma única vez para latência mínima (< 200ms)
    const _somSucesso = document.getElementById('som-sucesso');
    const _somErro = document.getElementById('som-erro');

    function _tocarSom(el) {
        if (!el) return;
        try {
            el.pause();          // Garante que pare qualquer reprodução anterior
            el.currentTime = 0;  // Reinicia do início (bipes rápidos em sequência)
            el.play().catch(() => { }); // Suprime erros de autoplay policy do browser
        } catch (e) { }
    }

    function acionarFeedbackSensorial(tipo) {
        const body = document.body;
        body.classList.remove('flash-success', 'flash-error');
        void body.offsetWidth; // Reflow forçado para reiniciar animação CSS

        if (tipo === 'success') {
            body.classList.add('flash-success');
            if (navigator.vibrate) navigator.vibrate([100]); // 1 vibração curta = Acerto
            _tocarSom(_somSucesso); // 🔊 Bipe curto (correto1Segundo.mp3)
        } else if (tipo === 'error') {
            body.classList.add('flash-error');
            if (navigator.vibrate) navigator.vibrate([200, 100, 200]); // 2 vibrações = Alerta
            _tocarSom(_somErro); // 🔊 Bipe longo 2s (Errado2Segundo.mp3) — trava até OK
        }
    }

    function atualizarStatusComunicacao(classe, texto) {
        const statusDiv = document.getElementById('status-comunicacao');
        if (statusDiv) {
            statusDiv.className = '';
            statusDiv.classList.add('status-' + classe);
            statusDiv.textContent = texto;
        }
    }

    function novaPromessaSimulada(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    window.atualizarProgresso = function () {
        const progressText = document.querySelector(".header-progress");
        if (!progressText) return { atual: 0, total: 1 };

        let partes = progressText.textContent.split("/");
        let atual = parseInt(partes[0], 10);
        let total = parseInt(partes[1], 10);

        // Incrementa o atual para dar efeito de avanço
        if (atual < total) atual++;
        progressText.textContent = `${atual}/${total}`;

        const porcentagem = (atual / total) * 100;
        const barra = document.querySelector(".barra-fill");
        if (barra) barra.style.width = porcentagem + "%";

        return { atual: atual, total: total };
    };

    window.mostrarModalErro = function (codigo) {
        const erroLabel = document.getElementById("codigo-erro");
        if (erroLabel) erroLabel.textContent = codigo;

        const modal = document.getElementById("modal-erro");
        if (modal) modal.classList.add("ativo");

        const erroSpan = document.querySelector(".ind-value[data-erros]");
        if (erroSpan) erroSpan.textContent = parseInt(erroSpan.textContent, 10) + 1;
    };

    window.fecharModalErro = function () {
        const modal = document.getElementById("modal-erro");
        if (modal) modal.classList.remove("ativo");

        const inputEndereco = document.getElementById("codigoEndereco") || document.getElementById("codigoPeca");
        if (inputEndereco) {
            inputEndereco.value = "";
            inputEndereco.focus();
        }
    };

    window.mostrarModalParcial = function () {
        const modal = document.getElementById("modal-parcial");
        if (modal) modal.classList.add("ativo");
    };

    window.fecharModalParcial = function () {
        const modal = document.getElementById("modal-parcial");
        if (modal) modal.classList.remove("ativo");
    };

    window.confirmarParcial = function () {
        window.fecharModalParcial();
        alert("Caixa fechada prematuramente. Status: PARCIAL.");
    };

    window.proximaCaixa = function () {
        const modal = document.getElementById("modal-sucesso");
        if (modal) modal.classList.add("ativo");
    };

    window.fecharModalSucesso = function () {
        const modal = document.getElementById("modal-sucesso");
        if (modal) modal.classList.remove("ativo");
        window.location.href = "/coletor/supervisor/";
    };


    // ==========================================================================
    // 4. IMPORTAÇÃO REAL (SHEETJS) - Dashboard Módulo
    // ==========================================================================
    function setupImportacao() {
        const uploadArea = document.getElementById("uploadArea");
        const fileInput = document.getElementById("fileInput");
        const filesList = document.getElementById("filesList");
        const btnImportar = document.getElementById("btnImportar");
        const btnLimpar = document.getElementById("btnLimpar");
        if (!uploadArea || !fileInput || !filesList || !btnImportar || !btnLimpar) return;

        let selectedFiles = [];

        uploadArea.addEventListener("click", function () { fileInput.click(); });
        uploadArea.addEventListener("dragover", function (e) {
            e.preventDefault();
            uploadArea.classList.add("dragover");
        });
        uploadArea.addEventListener("dragleave", function () {
            uploadArea.classList.remove("dragover");
        });
        uploadArea.addEventListener("drop", function (e) {
            e.preventDefault();
            uploadArea.classList.remove("dragover");
            handleFiles(e.dataTransfer.files);
        });
        fileInput.addEventListener("change", function (e) {
            handleFiles(e.target.files);
        });

        // BOTÃO IMPORTAR: Extração Real de Dados via SheetJS
        btnImportar.addEventListener("click", async function () {
            if (selectedFiles.length === 0) {
                alert("Selecione pelo menos um arquivo Excel/CSV.");
                return;
            }

            const btnOriginalText = btnImportar.innerHTML;
            btnImportar.innerHTML = "⏳ Extraindo Planilha...";
            btnImportar.style.opacity = "0.7";
            btnImportar.disabled = true;

            try {
                for (let file of selectedFiles) {
                    await lerEProcessarArquivoLocal(file);
                }

                alert("✅ Arquivo importado com sucesso! Os dados foram processados e salvos no Banco de Dados pelo Django.");

                selectedFiles = [];
                fileInput.value = "";
                renderFiles();

                window.location.reload();

            } catch (error) {
                console.error("Erro na leitura:", error);
                alert("❌ Erro. O arquivo é inválido ou a biblioteca SheetJS não foi carregada no HTML.");
            } finally {
                btnImportar.innerHTML = btnOriginalText;
                btnImportar.style.opacity = "1";
                btnImportar.disabled = false;
            }
        });

        btnLimpar.addEventListener("click", function () {
            selectedFiles = [];
            fileInput.value = "";
            renderFiles();
        });

        // Leitura Binária e conversão para JSON (Tecnologia Real)
        function lerEProcessarArquivoLocal(file) {
            return new Promise((resolve, reject) => {
                const reader = new FileReader();

                reader.onload = async function (e) {
                    try {
                        const data = new Uint8Array(e.target.result);
                        if (typeof XLSX === 'undefined') {
                            reject("SheetJS ausente."); return;
                        }
                        const workbook = XLSX.read(data, { type: 'array' });
                        const worksheet = workbook.Sheets[workbook.SheetNames[0]];
                        const jsonExtraido = XLSX.utils.sheet_to_json(worksheet);

                        console.log(`[DADOS EXTRAÍDOS] -> ${file.name}:`, jsonExtraido);

                        // Faz o envio real para o backend
                        try {
                            const res = await fetch('/api/v1/importar-pedidos/', {
                                method: 'POST',
                                headers: {
                                    'Content-Type': 'application/json',
                                    'X-CSRFToken': getCookie('csrftoken')
                                },
                                body: JSON.stringify({ arquivo: file.name, dados: jsonExtraido })
                            });
                            const result = await res.json();
                            if (!res.ok || result.status === 'erro') {
                                throw new Error(result.mensagem || "Erro na importação pelo servidor");
                            }
                            console.log(`[RESPOSTA SERVIDOR] ->`, result);
                            resolve(jsonExtraido);
                        } catch (err) {
                            reject(err);
                        }
                    } catch (err) {
                        reject(err);
                    }
                };
                reader.onerror = reject;
                reader.readAsArrayBuffer(file);
            });
        }

        // UX: Mostra arquivos na tela
        function handleFiles(files) {
            Array.from(files).forEach(function (file) {
                if (isValidFile(file)) selectedFiles.push(file);
            });
            renderFiles();
        }

        function isValidFile(file) {
            const validExtensions = [".csv", ".xlsx", ".xls"];
            const ext = "." + file.name.split(".").pop().toLowerCase();
            return validExtensions.includes(ext);
        }

        function formatFileSize(bytes) {
            if (bytes < 1024) return bytes + " B";
            if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + " KB";
            return (bytes / (1024 * 1024)).toFixed(1) + " MB";
        }

        function getFileIcon(filename) {
            const ext = filename.split(".").pop().toLowerCase();
            if (ext === "csv") return "📄";
            if (ext === "xlsx" || ext === "xls") return "📊";
            return "📁";
        }

        function renderFiles() {
            if (selectedFiles.length === 0) {
                filesList.innerHTML = '<div class="files-empty"><span class="empty-icon">📭</span><p>Nenhum arquivo selecionado</p></div>';
                return;
            }

            filesList.innerHTML = selectedFiles.map(function (file, index) {
                return '<div class="file-item"><span class="file-icon">' + getFileIcon(file.name) + '</span><div class="file-info"><span class="file-name">' + escapeHtml(file.name) + '</span><span class="file-size">' + formatFileSize(file.size) + '</span></div><button class="file-remove" data-index="' + index + '">✖</button></div>';
            }).join("");

            filesList.querySelectorAll(".file-remove").forEach(function (btn) {
                btn.addEventListener("click", function (e) {
                    selectedFiles.splice(parseInt(e.target.dataset.index, 10), 1);
                    renderFiles();
                });
            });
        }
    }

    // ==========================================================================
    // 5. RESTANTE DO DASHBOARD E PAINEL (Tabelas, Gráficos, Temas)
    // ==========================================================================

    function setupThemeToggle() {
        const toggle = document.getElementById("themeToggle");
        const icon = toggle ? toggle.querySelector(".theme-icon") : null;
        if (!toggle || !icon || toggle.dataset.bound === "true") return;

        const savedTheme = localStorage.getItem("theme");
        const initialTheme = savedTheme === "light" ? "light" : "";
        applyTheme(initialTheme, icon);

        toggle.addEventListener("click", function () {
            const current = document.body.getAttribute("data-theme");
            const next = current === "light" ? "" : "light";
            applyTheme(next, icon);
            localStorage.setItem("theme", next);

            icon.classList.add("spin");
            setTimeout(() => { icon.classList.remove("spin"); }, 200);
        });

        toggle.dataset.bound = "true";
    }

    function applyTheme(theme, icon) {
        document.body.setAttribute("data-theme", theme);
        icon.textContent = theme === "light" ? "☀️" : "🌙";
    }

    function atualizarData() {
        const dataAtual = document.getElementById("dataAtual");
        if (!dataAtual) return;
        const data = new Date();
        const opcoes = { day: "2-digit", month: "2-digit", year: "numeric" };
        dataAtual.textContent = data.toLocaleDateString("pt-BR", opcoes);
    }

    function calcularBarrasGrafico() {
        const barras = document.querySelectorAll("#graficoPPH .barra-group");
        if (!barras.length) return;
        const pphValues = Array.from(barras).map(barra => parseInt(barra.getAttribute("data-pph"), 10) || 0);
        const maxPPH = Math.max(...pphValues);
        if (!maxPPH) return;

        barras.forEach(barra => {
            const pph = parseInt(barra.getAttribute("data-pph"), 10) || 0;
            const barraEl = barra.querySelector(".barra");
            if (barraEl) barraEl.style.height = (pph / maxPPH) * 100 + "%";
        });
    }

    function setupKeyboardNav() {
        if (!document.querySelector(".nav-menu .nav-item")) return;

        document.addEventListener("keydown", function (e) {
            const navItems = document.querySelectorAll(".nav-menu .nav-item");
            const currentPage = window.location.href.split("/").pop();
            let currentIndex = Array.from(navItems).findIndex(item => item.getAttribute("href") === currentPage || currentPage === "");
            if (currentIndex === -1) currentIndex = Array.from(navItems).findIndex(item => item.classList.contains("active"));

            if (e.key === "ArrowLeft" && currentIndex > 0) {
                navigateToPage(navItems[currentIndex - 1]);
            } else if (e.key === "ArrowRight" && currentIndex < navItems.length - 1) {
                navigateToPage(navItems[currentIndex + 1]);
            }
        });
    }

    function navigateToPage(link) {
        document.body.classList.add("page-transition-out");
        setTimeout(() => { window.location.href = link.getAttribute("href"); }, 300);
    }

    function setupPainelOperacoes() {
        // ⚡ GUARD: Este painel usa dados reais via carregarEquipe() no template.
        // O mock OPERATORS_DATA NÃO deve sobrescrever os dados da API real.
        // Detectamos o painel real pelo atributo data-real-api no operatorsGrid.
        const operatorsGridEl = document.getElementById('operatorsGrid');
        if (operatorsGridEl && operatorsGridEl.hasAttribute('data-real-api')) return;

        window.painelElements = {
            operatorsGrid: document.getElementById("operatorsGrid"),
            exceptionsList: document.getElementById("exceptionsList"),
            searchInput: document.getElementById("searchInput"),
            tabButtons: document.querySelectorAll(".tab-button"),
            filterButtons: document.querySelectorAll(".filter-btn"),
            filterCurrents: document.querySelectorAll(".filter-current"),
            drawerOverlay: document.getElementById("drawerOverlay"),
            operatorDrawer: document.getElementById("operatorDrawer"),
            drawerClose: document.getElementById("drawerClose"),
            drawerInfo: document.getElementById("drawerInfo"),
            drawerTitle: document.getElementById("drawerTitle"),
            masterCodeOverlay: document.getElementById("masterCodeOverlay"),
            masterCodeExceptionId: document.getElementById("masterCodeExceptionId"),
            masterCodeInput: document.getElementById("masterCodeInput"),
            masterCodeCancel: document.getElementById("masterCodeCancel"),
            masterCodeConfirm: document.getElementById("masterCodeConfirm"),
            backButton: document.getElementById("backButton"),
            operadoresAtivos: document.getElementById("operadoresAtivos"),
            excecoes: document.getElementById("excecoes"),
            badgeExcecoes: document.getElementById("badgeExcecoes"),
            pphMedio: document.getElementById("pphMedio")
        };
        const elements = window.painelElements;
        if (!elements.operatorsGrid || !elements.exceptionsList) return;

        const state = {
            currentTab: "equipe", currentFilter: "hoje", searchQuery: "",
            operators: OPERATORS_DATA.slice(), exceptions: EXCEPTIONS_DATA.slice(),
            selectedOperator: null, selectedException: null, isDrawerOpen: false, isMasterCodeOpen: false
        };

        elements.tabButtons.forEach(btn => btn.addEventListener("click", () => switchTab(btn.dataset.tab)));
        elements.filterButtons.forEach(btn => btn.addEventListener("click", () => handleFilterClick(btn.dataset.filter)));
        if (elements.searchInput) elements.searchInput.addEventListener("input", debounce(e => handleSearch(e.target.value), 160));
        if (elements.drawerClose) elements.drawerClose.addEventListener("click", closeDrawer);
        if (elements.drawerOverlay) elements.drawerOverlay.addEventListener("click", closeDrawer);
        if (elements.masterCodeOverlay) elements.masterCodeOverlay.addEventListener("click", handleMasterCodeOverlayClick);
        if (elements.masterCodeCancel) elements.masterCodeCancel.addEventListener("click", closeMasterCodeModal);
        if (elements.masterCodeConfirm) elements.masterCodeConfirm.addEventListener("click", confirmMasterCode);
        if (elements.masterCodeInput) elements.masterCodeInput.addEventListener("keydown", e => { if (e.key === "Enter") confirmMasterCode(); });
        if (elements.backButton) elements.backButton.addEventListener("click", handleBack);

        document.addEventListener("keydown", e => {
            if (e.key !== "Escape") return;
            if (state.isMasterCodeOpen) closeMasterCodeModal();
            else if (state.isDrawerOpen) closeDrawer();
        });

        renderOperators();
        renderExceptions();
        updateIndicators();

        function switchTab(tabName) {
            state.currentTab = tabName;
            elements.tabButtons.forEach(btn => btn.classList.toggle("active", btn.dataset.tab === tabName));
            document.querySelectorAll(".tab-content").forEach(content => content.classList.toggle("active", content.id === "tab-" + tabName));
        }

        function handleFilterClick(filter) {
            const labels = { hoje: "Hoje", ontem: "Ontem", "7dias": "7 dias", "30dias": "30 dias", personalizado: "Personalizado" };
            state.currentFilter = filter;
            elements.filterButtons.forEach(btn => btn.classList.toggle("active", btn.dataset.filter === filter));
            elements.filterCurrents.forEach(curr => curr.textContent = labels[filter] || "Hoje");
        }

        function handleSearch(value) {
            const query = value.toLowerCase().trim();
            state.searchQuery = query;
            state.operators = query ? OPERATORS_DATA.filter(op => [op.name, op.id, op.location, op.caixa].join(" ").toLowerCase().includes(query)) : OPERATORS_DATA.slice();
            renderOperators();
        }

        window.renderOperators = function () {
            if (!window.painelElements) return;
            const elements = window.painelElements;
            state.operators = OPERATORS_DATA;
            if (state.operators.length === 0) {
                elements.operatorsGrid.innerHTML = `<div class="empty-state">Nenhum operador encontrado.</div>`;
                return;
            }
            elements.operatorsGrid.innerHTML = state.operators.map(createOperatorCard).join("");
            elements.operatorsGrid.querySelectorAll(".operator-card").forEach(card => {
                const openSelectedCard = () => openDrawer(card.dataset.operatorId);
                card.addEventListener("click", openSelectedCard);
                card.addEventListener("keydown", e => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); openSelectedCard(); } });
            });
        }

        function createOperatorCard(operator) {
            const signalIcon = operator.status === "error" ? createNoSignalIcon() : createSignalIcon();
            return `<article class="operator-card" data-operator-id="${escapeHtml(operator.id)}" tabindex="0"><div class="operator-header"><div class="operator-left"><span class="status-dot ${escapeHtml(operator.status)}"></span><div><div class="operator-name">${escapeHtml(operator.name)}</div><div class="operator-meta">${escapeHtml(operator.id)} - ${escapeHtml(operator.location)}</div></div></div>${signalIcon}</div><div class="operator-stats"><div class="stat-block"><span class="stat-label">PPH</span><strong class="stat-value">${operator.pph}</strong></div><div class="stat-block"><span class="stat-label">Caixa</span><strong class="stat-value">${escapeHtml(operator.caixa)}</strong></div><div class="stat-block"><span class="stat-label">Sinal</span><strong class="stat-value">${escapeHtml(operator.sinal)}</strong></div></div></article>`;
        }

        function createSignalIcon() { return `<svg class="operator-signal" width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 20h.01"/></svg>`; }
        function createNoSignalIcon() { return `<svg class="operator-signal error" width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 20h.01"/><path d="M4 4l16 16"/></svg>`; }

        function renderExceptions() {
            if (state.exceptions.length === 0) {
                elements.exceptionsList.innerHTML = `<tr><td class="exception-empty" colspan="5">Nenhuma exceção encontrada.</td></tr>`;
                return;
            }
            elements.exceptionsList.innerHTML = state.exceptions.map(createExceptionItem).join("");
            elements.exceptionsList.querySelectorAll(".authorize-btn").forEach(btn => btn.addEventListener("click", () => openMasterCodeModal(btn.dataset.exceptionId)));
        }

        function createExceptionItem(ex) {
            return `<tr class="exception-row"><td class="exception-id">${escapeHtml(ex.id)}</td><td class="exception-operator"><strong>${escapeHtml(ex.operator)}</strong><small>${escapeHtml(ex.time)}</small></td><td><span class="exception-type ${escapeHtml(ex.typeClass)}">${escapeHtml(ex.type)}</span></td><td class="exception-reason">${escapeHtml(ex.reason)}</td><td class="exception-action"><button class="authorize-btn" type="button" data-exception-id="${escapeHtml(ex.id)}">Autorizar</button></td></tr>`;
        }

        function openMasterCodeModal(exceptionId) {
            const exception = EXCEPTIONS_DATA.find(item => item.id === exceptionId);
            if (!exception || !elements.masterCodeOverlay) return;
            state.selectedException = exception;
            state.isMasterCodeOpen = true;
            elements.masterCodeExceptionId.textContent = exception.id;
            elements.masterCodeInput.value = "";
            elements.masterCodeOverlay.classList.add("active");
            elements.masterCodeOverlay.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
            setTimeout(() => elements.masterCodeInput.focus(), 0);
        }

        function closeMasterCodeModal() {
            state.isMasterCodeOpen = false;
            state.selectedException = null;
            if (!elements.masterCodeOverlay) return;
            elements.masterCodeOverlay.classList.remove("active");
            elements.masterCodeOverlay.setAttribute("aria-hidden", "true");
            elements.masterCodeInput.value = "";
            document.body.style.overflow = state.isDrawerOpen ? "hidden" : "";
        }

        function handleMasterCodeOverlayClick(event) { if (event.target === elements.masterCodeOverlay) closeMasterCodeModal(); }
        function confirmMasterCode() { closeMasterCodeModal(); }

        function openDrawer(operatorId) {
            const operator = OPERATORS_DATA.find(item => item.id === operatorId);
            if (!operator || !elements.operatorDrawer) return;
            state.selectedOperator = operator;
            state.isDrawerOpen = true;
            elements.drawerTitle.textContent = operator.name;
            elements.drawerInfo.innerHTML = createDrawerContent(operator);
            elements.drawerOverlay.classList.add("active");
            elements.operatorDrawer.classList.add("active");
            elements.operatorDrawer.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
        }

        function closeDrawer() {
            state.isDrawerOpen = false;
            if (elements.drawerOverlay) elements.drawerOverlay.classList.remove("active");
            if (elements.operatorDrawer) {
                elements.operatorDrawer.classList.remove("active");
                elements.operatorDrawer.setAttribute("aria-hidden", "true");
            }
            document.body.style.overflow = "";
        }

        function createDrawerContent(operator) {
            const details = operator.details;
            return `<section class="drawer-section"><div class="drawer-section-title">Informações gerais</div>${createDrawerRow("Matrícula", details.matricula)}${createDrawerRow("Setor", details.setor)}${createDrawerRow("Status", getStatusLabel(operator.status))}${createDrawerRow("Tempo online", details.tempoOnline)}</section><section class="drawer-section"><div class="drawer-section-title">Produtividade</div>${createDrawerRow("PPH", operator.pph)}${createDrawerRow("Acurácia", details.acuracia)}${createDrawerRow("Produção do dia", details.producaoDia)}</section><section class="drawer-section"><div class="drawer-section-title">Últimas caixas</div>${details.ultimasCaixas.map(c => createDrawerRow("Caixa", c)).join("")}</section><section class="drawer-section"><div class="drawer-section-title">Exceções</div>${createDrawerRow("Total do dia", details.excecoes)}</section><div class="drawer-actions"><button class="drawer-btn primary" type="button">Enviar mensagem</button><button class="drawer-btn" type="button">Ver histórico completo</button><button class="drawer-btn" type="button">Abrir perfil</button></div>`;
        }

        function createDrawerRow(label, value) { return `<div class="drawer-row"><span>${escapeHtml(String(label))}</span><strong>${escapeHtml(String(value))}</strong></div>`; }
        function getStatusLabel(status) { const labels = { online: "Online", idle: "Aguardando", error: "Atenção", offline: "Offline" }; return labels[status] || status; }

        function updateIndicators() {
            const onlineCount = OPERATORS_DATA.filter(op => op.status === "online").length;
            const totalCount = OPERATORS_DATA.length;
            const exceptionCount = EXCEPTIONS_DATA.length;
            const pphAverage = Math.round(OPERATORS_DATA.reduce((total, op) => total + op.pph, 0) / totalCount);

            elements.operadoresAtivos.textContent = `${onlineCount}/${totalCount}`;
            elements.excecoes.textContent = exceptionCount;
            elements.badgeExcecoes.textContent = exceptionCount;
            elements.pphMedio.textContent = pphAverage;
        }

        function handleBack() {
            if (window.history.length > 1) { window.history.back(); return; }
            window.location.href = "../../Dashboard MES/index/index.html";
        }
    }

    function debounce(callback, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(() => callback(...args), delay);
        };
    }

    function escapeHtml(value) {
        return String(value)
            .replaceAll("&", "&amp;")
            .replaceAll("<", "&lt;")
            .replaceAll(">", "&gt;")
            .replaceAll('"', "&quot;")
            .replaceAll("'", "&#039;");
    }

    // Utilitário para pegar o CSRF token do cookie (exigido pelo Django em POSTs)
    function getCookie(name) {
        let cookieValue = null;
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        return cookieValue;
    }

    // Expõe para escopos globais (inline scripts no HTML)
    window.getCookie = getCookie;

    window.baixarComoXLSX = async function (url, filename) {
        try {
            const response = await fetch(url);
            if (!response.ok) throw new Error("Erro na rede ou servidor.");
            const csvText = await response.text();

            // Reutiliza a biblioteca SheetJS (que já está na página)
            const workbook = XLSX.read(csvText, { type: 'string', raw: true });
            XLSX.writeFile(workbook, filename + '.xlsx');
        } catch (e) {
            alert("Erro ao gerar o arquivo XLSX: " + e.message);
        }
    };

}());