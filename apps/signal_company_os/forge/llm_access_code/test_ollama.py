from ollama_client import generate
from guard import enforce_three_words

def main():
    result = generate(
        prompt=(
            "Return exactly three lowercase words.\n"
            "No punctuation.\n"
            "No capitalization.\n"
            "Words separated by single spaces.\n"
            "Nothing else."
        ),
        model="phi3:mini",
    )

    enforce_three_words(result)
    print(result)

if __name__ == "__main__":
    main()

