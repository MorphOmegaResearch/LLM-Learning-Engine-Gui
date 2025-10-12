import os

def main():
  """Prints the menu and exits."""

  while True:
    print("\nSimple TUI App Menu:")
    print("1. Exit")

    choice = input("Enter your choice (1 or 2): ")

    if choice == '1':
      os._exit(0)  # Terminate the program
    else:
      print("Invalid choice.")


if __name__ == "__main__":
  main()
