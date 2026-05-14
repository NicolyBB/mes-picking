// ==========================================================================
// Arquivo Unificado de Scripts do Projeto Kyly MES (Dashboard + Coletor)
// Arquitetura: Offline-First, PWA, AJAX (Latência < 200ms) + Leitura Híbrida (Câmera, Laser e Manual)
// ==========================================================================

(function () {
    "use strict";

    // ==========================================================================
    // DADOS SIMULADOS (MOCK) - Dashboard
    // ==========================================================================
    const OPERATORS_DATA = [
        { id: "K-1042", name: "Carla Mendes", location: "Corredor A02", status: "online", pph: 142, caixa: "06772401", sinal: "agora", details: { matricula: "K-1042", setor: "Corredor A02", tempoOnline: "4h 32m", ultimasCaixas: ["06772401", "06772402", "06772403"], excecoes: 0, acuracia: "99.8%", producaoDia: "1.254 unidades" } },
        { id: "K-1188", name: "Bruno Lima", location: "Corredor B07", status: "online", pph: 128, caixa: "06772419", sinal: "12s", details: { matricula: "K-1188", setor: "Corredor B07", tempoOnline: "5h 15m", ultimasCaixas: ["06772419", "06772418", "06772417"], excecoes: 1, acuracia: "98.5%", producaoDia: "1.102 unidades" } },
        { id: "K-0987", name: "Patrícia Souza", location: "Corredor C03", status: "idle", pph: 95, caixa: "06772422", sinal: "2m", details: { matricula: "K-0987", setor: "Corredor C03", tempoOnline: "3h 45m", ultimasCaixas: ["06772422", "06772421", "06772420"], excecoes: 0, acuracia: "99.1%", producaoDia: "845 unidades" } },
        { id: "K-1230", name: "Diego Antunes", location: "Corredor D11", status: "error", pph: 0, caixa: "06772430", sinal: "7m", details: { matricula: "K-1230", setor: "Corredor D11", tempoOnline: "1h 20m", ultimasCaixas: ["06772430", "06772429"], excecoes: 3, acuracia: "95.2%", producaoDia: "512 unidades" } },
        { id: "K-1345", name: "Renata Cruz", location: "Corredor A05", status: "online", pph: 156, caixa: "06772441", sinal: "agora", details: { matricula: "K-1345", setor: "Corredor A05", tempoOnline: "6h", ultimasCaixas: ["06772441", "06772440", "06772439"], excecoes: 0, acuracia: "99.9%", producaoDia: "1.456 unidades" } },
        { id: "K-1502", name: "Felipe Gomes", location: "Corredor E02", status: "online", pph: 110, caixa: "06772455", sinal: "8s", details: { matricula: "K-1502", setor: "Corredor E02", tempoOnline: "4h 50m", ultimasCaixas: ["06772455", "06772454", "06772453"], excecoes: 2, acuracia: "98.7%", producaoDia: "998 unidades" } }
    ];

    const EXCEPTIONS_DATA = [
        { id: "EX-9981", operator: "Bruno Lima", time: "há 1 min", type: "Pular SKU", typeClass: "skip", reason: "Falta de peça no endereço B07.04.2A" },
        { id: "EX-9979", operator: "Patrícia Souza", time: "há 4 min", type: "Saldo Zero", typeClass: "balance", reason: "Ref 1000044 sem saldo físico" },
        { id: "EX-9975", operator: "Renata Cruz", time: "há 9 min", type: "Peça Danificada", typeClass: "damage", reason: "Ref 1000022 - costura aberta" }
    ];

    // INICIALIZAÇÃO PRINCIPAL
    document.addEventListener("DOMContentLoaded", function () {
        setupThemeToggle();
        setupKeyboardNav();
        atualizarData();
        calcularBarrasGrafico();
        setupImportacao();
        setupPainelOperacoes();
        
        // Habilita as leituras em todas as telas
        setupEntradasHibridas();
    });

    // ==========================================================================
    // 1. LEITURA HÍBRIDA (Câmera Real + Laser Datalogic + Digitação Manual)
    // ==========================================================================
    let html5QrcodeScanner = null;
    let contextoScanAtual = null; // Armazena qual campo estamos lendo (ex: codigoSupervisor)

    /**
     * Função chamada pelo botão "Escanear com a Câmera" nas telas HTML
     * @param {string} inputId - O ID do campo que receberá o valor lido
     */
    window.iniciarScannerCamera = function(inputId) {
        contextoScanAtual = inputId;
        const modal = document.getElementById('scanner-modal');
        if(!modal) {
            console.error("Modal da câmera não encontrado no HTML!");
            return;
        }
        
        modal.classList.remove('hidden');
        
        // Configura o Scanner nativo
        html5QrcodeScanner = new Html5QrcodeScanner(
            "reader", 
            { fps: 10, qrbox: {width: 250, height: 250} }, 
            false
        );
        
        html5QrcodeScanner.render(onScanSuccess, onScanFailure);
    };

    // Callback de Sucesso da Câmera
    function onScanSuccess(decodedText, decodedResult) {
        if (navigator.vibrate) navigator.vibrate(100); // Vibração física real
        
        window.fecharScanner();
        
        // Joga o valor lido no input correspondente e já chama a validação!
        if (contextoScanAtual) {
            const input = document.getElementById(contextoScanAtual);
            if(input) {
                input.value = decodedText;
                
                // Roteamento inteligente: Decide qual função chamar baseado na tela atual
                if(contextoScanAtual === 'codigoSupervisor') verificarSupervisor();
                else if(contextoScanAtual === 'codigoColaborador') verificarColaborador();
                else if(contextoScanAtual === 'codigoPapeleta') verificarPapeleta();
                else if(contextoScanAtual === 'codigoEndereco') verificarEndereco();
            }
        }
    }

    function onScanFailure(error) {
        // Ignorado intencionalmente. O scanner tenta ler vários frames por segundo.
    }

    window.fecharScanner = function() {
        if (html5QrcodeScanner) {
            html5QrcodeScanner.clear().catch(error => console.error("Erro ao limpar scanner", error));
            html5QrcodeScanner = null;
        }
        const modal = document.getElementById('scanner-modal');
        if (modal) modal.classList.add('hidden');
    };

    /**
     * Habilita a tecla ENTER para todos os inputs, suportando o Laser físico 
     * e a digitação manual do operador.
     */
    function setupEntradasHibridas() {
        const inputsDeLeitura = ['codigoSupervisor', 'codigoColaborador', 'codigoPapeleta', 'codigoEndereco'];
        
        inputsDeLeitura.forEach(id => {
            const input = document.getElementById(id);
            if (input) {
                // Foco automático para o laser já chegar lendo
                input.focus();
                
                // Se apertar Enter (o que o Laser do Datalogic faz automaticamente no final do bip)
                input.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') {
                        e.preventDefault(); // Evita recarregar a tela (submit form)
                        if(id === 'codigoSupervisor') verificarSupervisor();
                        else if(id === 'codigoColaborador') verificarColaborador();
                        else if(id === 'codigoPapeleta') verificarPapeleta();
                        else if(id === 'codigoEndereco') verificarEndereco();
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
        if(!input) return;
        const codigo = input.value.trim();

        if (codigo === "") {
            alert("Por favor, bip ou digite o código do supervisor.");
            return;
        }

        atualizarStatusComunicacao('processando', 'Validando Supervisor...');
        await novaPromessaSimulada(200); // Simulando latência de rede

        // Regra: Para a apresentação, o crachá do supervisor deve começar com SUP-
        if (codigo.toUpperCase().startsWith("SUP-") || codigo === "1234") {
            acionarFeedbackSensorial('success');
            // Avanço de página simulando SPA
            setTimeout(() => { window.location.href = "Passo2colaborador.html"; }, 300);
        } else {
            acionarFeedbackSensorial('error');
            alert("Acesso Negado: Código de supervisor não reconhecido no sistema.");
            input.value = "";
            input.focus();
            atualizarStatusComunicacao('off', 'Aguardando Leitura...');
        }
    };

    window.verificarColaborador = async function () {
        const input = document.getElementById("codigoColaborador");
        if(!input) return;
        const codigo = input.value.trim();

        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Validando Operador...');
        await novaPromessaSimulada(200);

        // Regra: Para a apresentação, o crachá do operador começa com COL-
        if (codigo.toUpperCase().startsWith("COL-") || codigo === "5678") {
            acionarFeedbackSensorial('success');
            setTimeout(() => { window.location.href = "../3.Abertura de caixa/index.html"; }, 300);
        } else {
            acionarFeedbackSensorial('error');
            alert("Erro: Operador não cadastrado ou sem turno ativo.");
            input.value = "";
        }
    };

    window.verificarPapeleta = async function () {
        const input = document.getElementById("codigoPapeleta");
        if(!input) return;
        const codigo = input.value.trim();

        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Carregando Rota da Caixa...');
        await novaPromessaSimulada(300); // Demora um pouco mais pois puxa a lista de itens

        // Regra: Papeletas iniciam com PAP-
        if (codigo.toUpperCase().startsWith("PAP-") || codigo === "0001") {
            acionarFeedbackSensorial('success');
            setTimeout(() => { window.location.href = "../4.Endereco de Picking/index.html"; }, 300);
        } else {
            acionarFeedbackSensorial('error');
            alert("Erro: Papeleta inválida ou já finalizada.");
            input.value = "";
        }
    };

    // O Fluxo Principal de Picking da Peça
    window.verificarEndereco = async function () {
        const input = document.getElementById("codigoEndereco");
        if(!input) return;
        const codigo = input.value.trim();

        if (codigo === "") return;

        atualizarStatusComunicacao('processando', 'Processando SKU...');
        
        // Mestre de Liberação (Bip do Supervisor para etiqueta rasgada)
        if (codigo.toUpperCase() === 'MASTER-LIBERACAO' || codigo.toUpperCase().startsWith('SUP-')) {
            acionarFeedbackSensorial('success');
            alert('Acesso Master Code: Item liberado manualmente pelo Supervisor.');
            // Força a validação avançar
            processarSucessoPicking(codigo);
            return;
        }

        await novaPromessaSimulada(150); // Requisição ultra rápida ao MES

        // Banco de dados Mock de Peças Corretas para a apresentação
        const enderecosValidos = ["78912340", "12345678", "1000017", "A02.01.4A", "KYLY-TESTE"];

        if (enderecosValidos.includes(codigo) || codigo.length > 5) { // Aceita também códigos grandes para facilitar testes de câmera
            processarSucessoPicking(codigo);
        } else {
            // ERRO (Peça não pertence à caixa ou sem saldo)
            acionarFeedbackSensorial('error');
            if (window.mostrarModalErro) {
                window.mostrarModalErro(codigo);
            } else {
                alert("Erro: A peça escaneada não pertence a este pedido!");
            }
            input.value = "";
            input.focus();
            atualizarStatusComunicacao('off', 'Aguardando Leitura...');
        }
    };

    function processarSucessoPicking(codigo) {
        acionarFeedbackSensorial('success');
        
        const enderecoDisplay = document.getElementById("enderecoAtual");
        if(enderecoDisplay) enderecoDisplay.textContent = "PEÇA VALIDADA: " + codigo;
        
        const input = document.getElementById("codigoEndereco");
        if(input) input.value = "";
        
        let resultado = window.atualizarProgresso ? window.atualizarProgresso() : null;
        
        // Se a barra de progresso encheu, finaliza a caixa
        if (resultado && resultado.atual >= resultado.total) {
            setTimeout(() => { window.location.href = "../5.FinalizaçãoPICK/index.html"; }, 400);
        } else {
            atualizarStatusComunicacao('off', 'Próxima peça. Aguardando...');
            if(input) input.focus();
        }
    }


    // ==========================================================================
    // 3. EFEITOS SENSORIAIS E UTILITÁRIOS (UI/UX Industrial)
    // ==========================================================================
    function acionarFeedbackSensorial(tipo) {
        const body = document.body;
        body.classList.remove('flash-success', 'flash-error');
        void body.offsetWidth; // Reflow forçado para reiniciar animação

        if (tipo === 'success') {
            body.classList.add('flash-success');
            if (navigator.vibrate) navigator.vibrate([100]); // 1 vibração curta
        } else if (tipo === 'error') {
            body.classList.add('flash-error');
            if (navigator.vibrate) navigator.vibrate([200, 100, 200]); // 2 vibrações (Aleta)
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
        if(!progressText) return { atual: 0, total: 1 };

        let partes = progressText.textContent.split("/");
        let atual = parseInt(partes[0], 10);
        let total = parseInt(partes[1], 10);
        
        // Incrementa o atual para dar efeito de avanço
        if (atual < total) atual++;
        progressText.textContent = `${atual}/${total}`;

        const porcentagem = (atual / total) * 100;
        const barra = document.querySelector(".barra-fill");
        if(barra) barra.style.width = porcentagem + "%";
        
        return { atual: atual, total: total };
    };

    window.mostrarModalErro = function (codigo) {
        const erroLabel = document.getElementById("codigo-erro");
        if(erroLabel) erroLabel.textContent = codigo;
        
        const modal = document.getElementById("modal-erro");
        if(modal) modal.classList.add("ativo");
        
        const erroSpan = document.querySelector(".ind-value[data-erros]");
        if (erroSpan) erroSpan.textContent = parseInt(erroSpan.textContent, 10) + 1;
    };

    window.fecharModal = function () {
        const modal = document.getElementById("modal-erro");
        if(modal) modal.classList.remove("ativo");
        
        const inputEndereco = document.getElementById("codigoEndereco");
        if(inputEndereco) {
            inputEndereco.value = "";
            inputEndereco.focus();
        }
    };

    window.mostrarModalParcial = function () {
        const modal = document.getElementById("modal-parcial");
        if(modal) modal.classList.add("ativo");
    };

    window.fecharModalParcial = function () {
        const modal = document.getElementById("modal-parcial");
        if(modal) modal.classList.remove("ativo");
    };

    window.confirmarParcial = function () {
        window.fecharModalParcial();
        alert("Caixa fechada prematuramente. Status: PARCIAL.");
    };

    window.proximaCaixa = function () {
        const modal = document.getElementById("modal-sucesso");
        if(modal) modal.classList.add("ativo");
    };

    window.fecharModalSucesso = function () {
        const modal = document.getElementById("modal-sucesso");
        if(modal) modal.classList.remove("ativo");
        window.location.href = "../1.Aguardandosupervisor/index.html";
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
                
                alert("✅ Arquivo processado com sucesso! Os dados JSON reais foram extraídos no F12 (Console) e estão prontos para o Django.");
                
                selectedFiles = [];
                fileInput.value = "";
                renderFiles();

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
                        await new Promise(r => setTimeout(r, 600)); // Delay estético
                        resolve(jsonExtraido);
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
        const elements = {
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
            elements.filterCurrents.forEach(curr => current.textContent = labels[filter] || "Hoje");
        }

        function handleSearch(value) {
            const query = value.toLowerCase().trim();
            state.searchQuery = query;
            state.operators = query ? OPERATORS_DATA.filter(op => [op.name, op.id, op.location, op.caixa].join(" ").toLowerCase().includes(query)) : OPERATORS_DATA.slice();
            renderOperators();
        }

        function renderOperators() {
            if (state.operators.length === 0) {
                elements.operatorsGrid.innerHTML = `<div class="empty-state">Nenhum operador encontrado para "${escapeHtml(state.searchQuery)}".</div>`;
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

}());