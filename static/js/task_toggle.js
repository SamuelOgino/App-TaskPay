// static/js/task_toggle.js
document.addEventListener('DOMContentLoaded', function() {
    
    // 1. Encontra TODOS os botões 'Concluir' na página
    const toggleButtons = document.querySelectorAll('.btn-toggle');
    
    toggleButtons.forEach(button => {
        const targetId = button.getAttribute('data-target');
        const targetFormContainer = document.getElementById(targetId);
        
        // 2. Encontra o botão 'Cancelar' específico dentro desse formulário
        const cancelButton = targetFormContainer ? targetFormContainer.querySelector('.btn-cancel') : null;

        // 3. Se não encontrar o formulário ou o botão cancelar, não faz nada
        if (!targetFormContainer || !cancelButton) {
            return;
        }

        // 4. Ação de Abrir o Formulário (Clique em "Concluir")
        button.addEventListener('click', () => {
            // Oculta o botão "Concluir"
            button.style.display = 'none';
            // Mostra o container do formulário
            targetFormContainer.classList.add('active');
        });

        // 5. Ação de Fechar o Formulário (Clique em "Cancelar")
        cancelButton.addEventListener('click', () => {
            // Mostra o botão "Concluir" novamente
            button.style.display = 'block';
            // Oculta o container do formulário
            targetFormContainer.classList.remove('active');
        });
    });

    // ===============================================
    // == NOVA LÓGICA (Acionar o botão pela URL) ==
    // ===============================================
    function triggerTaskFromAnchor() {
        const hash = window.location.hash; // Pega (ex: #tarefa-123)

        // Verifica se existe uma âncora
        if (hash) {
            try {
                // Tenta encontrar o card que tem esse ID
                const targetCard = document.querySelector(hash);
                
                if (targetCard) {
                    // Encontra o botão "Concluir" DENTRO desse card
                    const toggleButton = targetCard.querySelector('.btn-toggle');
                    
                    if (toggleButton) {
                        // Simula o clique no botão
                        toggleButton.click();
                    }
                }
            } catch (e) {
                console.error("Erro ao tentar acionar a âncora da tarefa:", e);
            }
        }
    }
    triggerTaskFromAnchor();

    // ===============================================
    // == NOVA LÓGICA (Auto-submit do formulário de foto) ==
    // ===============================================
    
    // 1. Encontra TODOS os inputs de arquivo
    const fileInputs = document.querySelectorAll('.file-input');

    fileInputs.forEach(input => {
        // 2. Adiciona um ouvinte para o evento 'change'
        input.addEventListener('change', function() {
            
            // 3. Verifica se um arquivo foi realmente selecionado
            if (this.files.length > 0) {
                
                // 4. Encontra o <form> pai mais próximo
                const form = this.closest('form');
                if (form) {
                    
                    // (Opcional) Mostra um feedback de "Enviando..."
                    const label = form.querySelector('label.btn-primary');
                    if(label) {
                        label.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i> Enviando...';
                    }
                    
                    // Esconde o botão "Cancelar" para evitar confusão
                    const formContainer = this.closest('.submission-form-container');
                    if(formContainer){
                        const cancelBtn = formContainer.querySelector('.btn-cancel');
                        if(cancelBtn) cancelBtn.style.display = 'none';
                    }

                    // 5. Envia o formulário
                    form.submit();
                }
            }
        });
    });
});

