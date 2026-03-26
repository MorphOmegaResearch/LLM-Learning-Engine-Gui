import pyperclip
from providers import get_provider
from workflow_engine import WorkflowEngine
from utils import read_context_from_source

def handle_cli_request(args):
    """
    Handles the command-line request, routing to the workflow engine
    or performing a simple, direct AI call.
    """
    # If a workflow file is specified, use the WorkflowEngine
    if args.workflow:
        engine = WorkflowEngine(args)
        engine.run()
        return

    # --- Otherwise, perform a simple one-shot request ---
    print("CLI mode: Performing direct AI call.")

    # 1. Get context
    context, error = read_context_from_source(args.context_file, args.context_clipboard)
    if error:
        print(error)
        return
    
    # 2. Get prompt
    prompt_instruction = ""
    if args.prompt:
        prompt_instruction = args.prompt
    elif args.prompt_file:
        # This is a simplified version of reading a prompt file
        try:
            with open(args.prompt_file, 'r', encoding='utf-8') as f:
                prompt_instruction = f.read()
        except FileNotFoundError:
            print(f"Error: Prompt file not found at {args.prompt_file}")
            return
    
    if not prompt_instruction:
        print("Error: A prompt is required for a direct call. Use --prompt or --prompt-file.")
        return

    full_prompt = f"{prompt_instruction}\n\nContent:\n{context}"

    # 3. Execute if requested
    if args.execute:
        provider_name = args.provider or 'ollama'
        provider = get_provider(provider_name)
        if not provider:
            print(f"Error: Provider '{provider_name}' not found.")
            return
        
        try:
            print(f"\n--- Calling AI Provider: {provider_name} ---")
            ai_output = provider.execute(full_prompt, args)
            
            print("--- AI Output ---")
            print(ai_output)
            print("-----------------")

            # 4. Save output if requested
            if args.output_file:
                try:
                    with open(args.output_file, 'w', encoding='utf-8') as f:
                        f.write(ai_output)
                    print(f"\nOutput saved to: {args.output_file}")
                except Exception as e:
                    print(f"Error saving output file: {e}")

        except Exception as e:
            print(f"\nAn error occurred during AI execution: {e}")
    else:
        print("\n--execute flag not provided. AI call was not made.")
        print("Prompt and context are ready. Use --execute to run.")
