# ASR Speech Recognition Refinement Task

## User Dictionary
{hotwords}

## Instructions
1. Correct obvious speech recognition errors
2. Remove obvious repetitions and stuttering
3. Refer to the user dictionary, only replace when pronunciation is completely identical but ASR recognition differs from the user dictionary, such as personal names and proper nouns. ASR is quite accurate for pronunciation recognition, so only replace if you are very confident the pronunciation is completely identical, otherwise preserve the original text instead of replacing.
4. Wrap your answer with xml tag, Output Format: <compare> your thinking of whether to replace the word, with detailed phonetic analysis using pinyin or phonetic transcription, and detailed semantic analysis, within two sentences </compare> <correct> the corrected text in user's language</correct>

## User ASR Recognition Result
"""{user_input}"""