// Script unico do projeto Kyly.
(function () {
    "use strict";

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

    document.addEventListener("DOMContentLoaded", function () {
        setupThemeToggle();
        setupKeyboardNav();
        atualizarData();
        calcularBarrasGrafico();
        setupImportacao();
        setupPainelOperacoes();
        setupEnderecoPicking();
    });

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
            setTimeout(function () {
                icon.classList.remove("spin");
            }, 200);
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

    function updateDateTime() {
        const dataAtual = document.getElementById("dataAtual");
        if (!dataAtual) return;

        const now = new Date();
        const options = { day: "2-digit", month: "2-digit", year: "numeric", hour: "2-digit", minute: "2-digit" };
        dataAtual.textContent = now.toLocaleDateString("pt-BR", options);
    }

    function calcularBarrasGrafico() {
        const barras = document.querySelectorAll("#graficoPPH .barra-group");
        if (!barras.length) return;

        const pphValues = Array.from(barras).map(function (barra) {
            return parseInt(barra.getAttribute("data-pph"), 10) || 0;
        });
        const maxPPH = Math.max(...pphValues);
        if (!maxPPH) return;

        barras.forEach(function (barra) {
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
            let currentIndex = Array.from(navItems).findIndex(function (item) {
                return item.getAttribute("href") === currentPage || currentPage === "";
            });

            if (currentIndex === -1) {
                currentIndex = Array.from(navItems).findIndex(function (item) {
                    return item.classList.contains("active");
                });
            }

            if (e.key === "ArrowLeft" && currentIndex > 0) {
                navigateToPage(navItems[currentIndex - 1]);
            } else if (e.key === "ArrowRight" && currentIndex < navItems.length - 1) {
                navigateToPage(navItems[currentIndex + 1]);
            }
        });
    }

    function navigateToPage(link) {
        document.body.classList.add("page-transition-out");
        setTimeout(function () {
            window.location.href = link.getAttribute("href");
        }, 300);
    }

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
        btnImportar.addEventListener("click", function () {
            if (selectedFiles.length === 0) {
                alert("Selecione pelo menos um arquivo para importar");
                return;
            }
            alert("Importando " + selectedFiles.length + " arquivo(s)...");
        });
        btnLimpar.addEventListener("click", function () {
            selectedFiles = [];
            fileInput.value = "";
            renderFiles();
        });

        updateDateTime();
        setInterval(updateDateTime, 60000);

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
            currentTab: "equipe",
            currentFilter: "hoje",
            searchQuery: "",
            operators: OPERATORS_DATA.slice(),
            exceptions: EXCEPTIONS_DATA.slice(),
            selectedOperator: null,
            selectedException: null,
            isDrawerOpen: false,
            isMasterCodeOpen: false
        };

        elements.tabButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                switchTab(button.dataset.tab);
            });
        });
        elements.filterButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                handleFilterClick(button.dataset.filter);
            });
        });
        if (elements.searchInput) {
            elements.searchInput.addEventListener("input", debounce(function (event) {
                handleSearch(event.target.value);
            }, 160));
        }
        if (elements.drawerClose) elements.drawerClose.addEventListener("click", closeDrawer);
        if (elements.drawerOverlay) elements.drawerOverlay.addEventListener("click", closeDrawer);
        if (elements.masterCodeOverlay) elements.masterCodeOverlay.addEventListener("click", handleMasterCodeOverlayClick);
        if (elements.masterCodeCancel) elements.masterCodeCancel.addEventListener("click", closeMasterCodeModal);
        if (elements.masterCodeConfirm) elements.masterCodeConfirm.addEventListener("click", confirmMasterCode);
        if (elements.masterCodeInput) {
            elements.masterCodeInput.addEventListener("keydown", function (event) {
                if (event.key === "Enter") confirmMasterCode();
            });
        }
        if (elements.backButton) elements.backButton.addEventListener("click", handleBack);

        document.addEventListener("keydown", function (event) {
            if (event.key !== "Escape") return;
            if (state.isMasterCodeOpen) {
                closeMasterCodeModal();
                return;
            }
            if (state.isDrawerOpen) closeDrawer();
        });

        renderOperators();
        renderExceptions();
        updateIndicators();

        function switchTab(tabName) {
            state.currentTab = tabName;
            elements.tabButtons.forEach(function (button) {
                button.classList.toggle("active", button.dataset.tab === tabName);
            });
            document.querySelectorAll(".tab-content").forEach(function (content) {
                content.classList.toggle("active", content.id === "tab-" + tabName);
            });
        }

        function handleFilterClick(filter) {
            const labels = { hoje: "Hoje", ontem: "Ontem", "7dias": "7 dias", "30dias": "30 dias", personalizado: "Personalizado" };
            state.currentFilter = filter;
            elements.filterButtons.forEach(function (button) {
                button.classList.toggle("active", button.dataset.filter === filter);
            });
            elements.filterCurrents.forEach(function (current) {
                current.textContent = labels[filter] || "Hoje";
            });
        }

        function handleSearch(value) {
            const query = value.toLowerCase().trim();
            state.searchQuery = query;
            state.operators = query ? OPERATORS_DATA.filter(function (operator) {
                return [operator.name, operator.id, operator.location, operator.caixa].join(" ").toLowerCase().includes(query);
            }) : OPERATORS_DATA.slice();
            renderOperators();
        }

        function renderOperators() {
            if (state.operators.length === 0) {
                elements.operatorsGrid.innerHTML = '<div class="empty-state">Nenhum operador encontrado para "' + escapeHtml(state.searchQuery) + '".</div>';
                return;
            }

            elements.operatorsGrid.innerHTML = state.operators.map(createOperatorCard).join("");
            elements.operatorsGrid.querySelectorAll(".operator-card").forEach(function (card) {
                const openSelectedCard = function () {
                    openDrawer(card.dataset.operatorId);
                };
                card.addEventListener("click", openSelectedCard);
                card.addEventListener("keydown", function (event) {
                    if (event.key === "Enter" || event.key === " ") {
                        event.preventDefault();
                        openSelectedCard();
                    }
                });
            });
        }

        function createOperatorCard(operator) {
            const signalIcon = operator.status === "error" ? createNoSignalIcon() : createSignalIcon();
            return '<article class="operator-card" data-operator-id="' + escapeHtml(operator.id) + '" tabindex="0"><div class="operator-header"><div class="operator-left"><span class="status-dot ' + escapeHtml(operator.status) + '"></span><div><div class="operator-name">' + escapeHtml(operator.name) + '</div><div class="operator-meta">' + escapeHtml(operator.id) + ' - ' + escapeHtml(operator.location) + '</div></div></div>' + signalIcon + '</div><div class="operator-stats"><div class="stat-block"><span class="stat-label">PPH</span><strong class="stat-value">' + operator.pph + '</strong></div><div class="stat-block"><span class="stat-label">Caixa</span><strong class="stat-value">' + escapeHtml(operator.caixa) + '</strong></div><div class="stat-block"><span class="stat-label">Sinal</span><strong class="stat-value">' + escapeHtml(operator.sinal) + '</strong></div></div></article>';
        }

        function createSignalIcon() {
            return '<svg class="operator-signal" width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 20h.01"/></svg>';
        }

        function createNoSignalIcon() {
            return '<svg class="operator-signal error" width="17" height="17" viewBox="0 0 24 24" aria-hidden="true"><path d="M5 12.5a10 10 0 0 1 14 0"/><path d="M8.5 16a5 5 0 0 1 7 0"/><path d="M12 20h.01"/><path d="M4 4l16 16"/></svg>';
        }

        function renderExceptions() {
            if (state.exceptions.length === 0) {
                elements.exceptionsList.innerHTML = '<tr><td class="exception-empty" colspan="5">Nenhuma exceção encontrada.</td></tr>';
                return;
            }
            elements.exceptionsList.innerHTML = state.exceptions.map(createExceptionItem).join("");
            elements.exceptionsList.querySelectorAll(".authorize-btn").forEach(function (button) {
                button.addEventListener("click", function () {
                    openMasterCodeModal(button.dataset.exceptionId);
                });
            });
        }

        function createExceptionItem(exception) {
            return '<tr class="exception-row"><td class="exception-id">' + escapeHtml(exception.id) + '</td><td class="exception-operator"><strong>' + escapeHtml(exception.operator) + '</strong><small>' + escapeHtml(exception.time) + '</small></td><td><span class="exception-type ' + escapeHtml(exception.typeClass) + '">' + escapeHtml(exception.type) + '</span></td><td class="exception-reason">' + escapeHtml(exception.reason) + '</td><td class="exception-action"><button class="authorize-btn" type="button" data-exception-id="' + escapeHtml(exception.id) + '">Autorizar</button></td></tr>';
        }

        function openMasterCodeModal(exceptionId) {
            const exception = EXCEPTIONS_DATA.find(function (item) { return item.id === exceptionId; });
            if (!exception || !elements.masterCodeOverlay) return;

            state.selectedException = exception;
            state.isMasterCodeOpen = true;
            elements.masterCodeExceptionId.textContent = exception.id;
            elements.masterCodeInput.value = "";
            elements.masterCodeOverlay.classList.add("active");
            elements.masterCodeOverlay.setAttribute("aria-hidden", "false");
            document.body.style.overflow = "hidden";
            setTimeout(function () { elements.masterCodeInput.focus(); }, 0);
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

        function handleMasterCodeOverlayClick(event) {
            if (event.target === elements.masterCodeOverlay) closeMasterCodeModal();
        }

        function confirmMasterCode() {
            closeMasterCodeModal();
        }

        function openDrawer(operatorId) {
            const operator = OPERATORS_DATA.find(function (item) { return item.id === operatorId; });
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
            return '<section class="drawer-section"><div class="drawer-section-title">Informações gerais</div>' + createDrawerRow("Matrícula", details.matricula) + createDrawerRow("Setor", details.setor) + createDrawerRow("Status", getStatusLabel(operator.status)) + createDrawerRow("Tempo online", details.tempoOnline) + '</section><section class="drawer-section"><div class="drawer-section-title">Produtividade</div>' + createDrawerRow("PPH", operator.pph) + createDrawerRow("Acurácia", details.acuracia) + createDrawerRow("Produção do dia", details.producaoDia) + '</section><section class="drawer-section"><div class="drawer-section-title">Últimas caixas</div>' + details.ultimasCaixas.map(function (caixa) { return createDrawerRow("Caixa", caixa); }).join("") + '</section><section class="drawer-section"><div class="drawer-section-title">Exceções</div>' + createDrawerRow("Total do dia", details.excecoes) + '</section><div class="drawer-actions"><button class="drawer-btn primary" type="button">Enviar mensagem</button><button class="drawer-btn" type="button">Ver histórico completo</button><button class="drawer-btn" type="button">Abrir perfil</button></div>';
        }

        function createDrawerRow(label, value) {
            return '<div class="drawer-row"><span>' + escapeHtml(String(label)) + '</span><strong>' + escapeHtml(String(value)) + '</strong></div>';
        }

        function getStatusLabel(status) {
            const labels = { online: "Online", idle: "Aguardando", error: "Atenção", offline: "Offline" };
            return labels[status] || status;
        }

        function updateIndicators() {
            const onlineCount = OPERATORS_DATA.filter(function (operator) { return operator.status === "online"; }).length;
            const totalCount = OPERATORS_DATA.length;
            const exceptionCount = EXCEPTIONS_DATA.length;
            const pphAverage = Math.round(OPERATORS_DATA.reduce(function (total, operator) {
                return total + operator.pph;
            }, 0) / totalCount);

            elements.operadoresAtivos.textContent = onlineCount + "/" + totalCount;
            elements.excecoes.textContent = exceptionCount;
            elements.badgeExcecoes.textContent = exceptionCount;
            elements.pphMedio.textContent = pphAverage;
        }

        function handleBack() {
            if (window.history.length > 1) {
                window.history.back();
                return;
            }
            window.location.href = "../../Dashboard MES/index/index.html";
        }
    }

    function setupEnderecoPicking() {
        const codigoEndereco = document.getElementById("codigoEndereco");
        if (!codigoEndereco) return;

        codigoEndereco.addEventListener("keypress", function (e) {
            if (e.key === "Enter") window.verificarEndereco();
        });
        window.atualizarProgresso();
    }

    function debounce(callback, delay) {
        let timeoutId;
        return function (...args) {
            clearTimeout(timeoutId);
            timeoutId = setTimeout(function () {
                callback(...args);
            }, delay);
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

    window.simularBip = function () {
        window.location.href = "../2.Passocracha/index.html";
    };

    window.verificarSupervisor = function () {
        const codigo = document.getElementById("codigoSupervisor").value.trim();
        if (codigo !== "") {
            window.location.href = "Passo2colaborador.html";
        } else {
            alert("Código inválido. Bipe o crachá do supervisor.");
        }
    };

    window.verificarColaborador = function () {
        const codigo = document.getElementById("codigoColaborador").value.trim();
        if (codigo !== "") {
            window.location.href = "../3.Abertura de caixa/index.html";
        } else {
            alert("Código inválido. Bipe o crachá do colaborador.");
        }
    };

    window.verificarPapeleta = function () {
        const codigo = document.getElementById("codigoPapeleta").value.trim();
        if (codigo !== "") {
            window.location.href = "../4.Endereco de Picking/index.html";
        } else {
            alert("Código inválido. Bipe a papeleta.");
        }
    };

    window.atualizarProgresso = function () {
        const progressText = document.querySelector(".header-progress").textContent;
        const partes = progressText.split("/");
        const atual = parseInt(partes[0], 10);
        const total = parseInt(partes[1], 10);
        const porcentagem = (atual / total) * 100;
        document.querySelector(".barra-fill").style.width = porcentagem + "%";
        return { atual: atual, total: total };
    };

    window.mostrarModalErro = function (codigo) {
        document.getElementById("codigo-erro").textContent = codigo;
        document.getElementById("modal-erro").classList.add("ativo");
        const erroSpan = document.querySelector(".ind-value[data-erros]");
        if (erroSpan) erroSpan.textContent = parseInt(erroSpan.textContent, 10) + 1;
    };

    window.fecharModal = function () {
        document.getElementById("modal-erro").classList.remove("ativo");
        document.getElementById("codigoEndereco").value = "";
        document.getElementById("codigoEndereco").focus();
    };

    window.mostrarModalParcial = function () {
        document.getElementById("modal-parcial").classList.add("ativo");
    };

    window.fecharModalParcial = function () {
        document.getElementById("modal-parcial").classList.remove("ativo");
    };

    window.confirmarParcial = function () {
        window.fecharModalParcial();
        alert("Caixa marcada como PARCIAL!");
    };

    window.verificarEndereco = function () {
        const codigo = document.getElementById("codigoEndereco").value.trim();
        if (codigo === "") {
            alert("Código inválido. Bipe o código da peça.");
            return;
        }

        const enderecosValidos = ["78912340", "12345678", "98765432", "A02.01.4A"];
        if (!enderecosValidos.includes(codigo)) {
            window.mostrarModalErro(codigo);
            return;
        }

        const resultado = window.atualizarProgresso();
        document.getElementById("enderecoAtual").textContent = codigo;
        document.getElementById("codigoEndereco").value = "";

        if (resultado.atual >= resultado.total) {
            window.location.href = "../5.FinalizaçãoPICK/index.html";
        }
    };

    window.proximaCaixa = function () {
        document.getElementById("modal-sucesso").classList.add("ativo");
    };

    window.fecharModalSucesso = function () {
        document.getElementById("modal-sucesso").classList.remove("ativo");
        window.location.href = "../1.Aguardandosupervisor/index.html";
    };
}());
