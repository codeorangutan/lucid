import logging

# DSM-5 criteria mapped to the actual ASRS question text and number
DSM5_ASRS_MAPPING = [
    # Criterion A: Inattention
    ("A1: Often fails to give close attention to details or makes careless mistakes", "Q7: How often do you make careless mistakes when you have to work on a boring or difficult project?", 7),
    ("A2: Often has difficulty sustaining attention in tasks or play activities", "Q8: How often do you have difficulty keeping your attention when you are doing boring or repetitive work?", 8),
    ("A3: Often does not seem to listen when spoken to directly", "Q9: How often do you have difficulty concentrating on what people say to you, even when they are speaking to you directly?", 9),
    ("A4: Often does not follow through on instructions and fails to finish duties", "Q1: How often do you have trouble wrapping up the final details of a project, once the challenging parts have been done?", 1),
    ("A5: Often has difficulty organizing tasks and activities", "Q2: How often do you have difficulty getting things in order when you have to do a task that requires organization?", 2),
    ("A6: Often avoids or is reluctant to engage in tasks requiring sustained mental effort", "Q4: When you have a task that requires a lot of thought, how often do you avoid or delay getting started?", 4),
    ("A7: Often loses things necessary for tasks or activities", "Q10: How often do you misplace or have difficulty finding things at home or at work?", 10),
    ("A8: Is often easily distracted by extraneous stimuli", "Q11: How often are you distracted by activity or noise around you?", 11),
    ("A9: Is often forgetful in daily activities", "Q3: How often do you have problems remembering appointments or obligations?", 3),
    # Criterion B: Hyperactivity and Impulsivity
    ("B1: Often fidgets or squirms in seat", "Q5: How often do you fidget or squirm with your hands or feet when you have to sit down for a long time?", 5),
    ("B2: Often leaves seat in situations when remaining seated is expected", "Q12: How often do you leave your seat in meetings or other situations in which you are expected to remain seated?", 12),
    ("B3: Often runs about or climbs in situations where it is inappropriate", "Q13: How often do you feel restless or fidgety?", 13),
    ("B4: Often unable to play or engage in leisure activities quietly", "Q14: How often do you have difficulty unwinding and relaxing when you have time to yourself?", 14),
    ("B5: Is often 'on the go', acting as if 'driven by a motor'", "Q6: How often do you feel overly active and compelled to do things, like you were driven by a motor?", 6),
    ("B6: Often talks excessively", "Q15: How often do you find yourself talking too much when you are in social situations?", 15),
    ("B7: Often blurts out an answer before a question has been completed", "Q16: When you're in a conversation, how often do you find yourself finishing the sentences of the people you are talking to, before they can finish them themselves?", 16),
    ("B8: Often has difficulty waiting his or her turn", "Q17: How often do you have difficulty waiting your turn in situations when turn taking is required?", 17),
    ("B9: Often interrupts or intrudes on others", "Q18: How often do you interrupt others when they are busy?", 18)
]

RESPONSE_SCORES = {
    "Never": 0,
    "Rarely": 1,
    "Sometimes": 2,
    "Often": 3,
    "Very Often": 4
}

# Questions where "Sometimes" (score of 2) is sufficient to meet criteria
LOWER_THRESHOLD_QUESTIONS = {1, 2, 3, 9, 12, 16, 18}

def is_met(response, question_number):
    """
    Determine if DSM-5 criterion is met based on ASRS response and question number.

    Args:
        response (str): The ASRS response text ("Never", "Rarely", "Sometimes", "Often", "Very Often")
        question_number (int): The ASRS question number (1-18)

    Returns:
        bool: True if criterion is met, False otherwise
    """
    score = RESPONSE_SCORES.get(response, None)
    if score is None:
        logging.warning(f"Unknown ASRS response: '{response}' for question {question_number}")
        return False
    if question_number in LOWER_THRESHOLD_QUESTIONS:
        return score >= 2  # Sometimes (2) or higher
    else:
        return score >= 3  # Often (3) or Very Often (4)