from treys import Evaluator, Card

def cards_parser(cards: dict):
    new_dict = {}
    for key in cards.keys():
        new_dict[key] = []
    for owner, card in cards.items():
        for values in card:
            if values[1] == 10:
                values[1] = 'T'
            new_card = f'{values[1]}{values[0].lower()}'
            new_dict[owner].append(new_card)
    return new_dict


def check_the_winner(cards: dict):
    evaluator = Evaluator()
    print(cards, "Cards dict")
    cards = cards_parser(cards)
    table_cards = [Card.new(card) for card in cards.get('table')]

    cards_list = []
    for owner, cards in cards.items():
        if owner != 'table':
            cards_list.append([int(owner), [Card().new(card) for card in cards]])
    evaluates = []

    for user_cards in cards_list:
        ev = evaluator.evaluate(user_cards[1], table_cards)
        cls = evaluator.get_rank_class(ev)
        cls_str = evaluator.class_to_string(cls)
        print(f'cls_str: {cls_str}')
        evaluates.append([user_cards[0], ev, cls_str])

    return [i for i in evaluates if i[1] == min([evaluate[1] for evaluate in evaluates])]