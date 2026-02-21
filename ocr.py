from paddleocr import PaddleOCR,draw_ocr
from pprint import pprint
from pathlib import Path
import re
import difflib

def get_receipt_lines(ocr_output, epsilon=5):
    """
    Given the output of the OCR model, return the lines of the receipt.
    ocr_output: first entry of output of PaddleOCR.ocr()
    epsilon: the maximum pixel difference in y-coordinates for two lines to be considered on the same line
    """
    # lines go left to right, then top to bottom

    def calculate_top_slope_and_intercept(bounding_box):
        """
        calculate the slope and intercept of the top line of the bounding box
        """
        top_left = bounding_box[0]
        top_right = bounding_box[1]

        x1 = top_left[0]
        y1 = top_left[1]
        x2 = top_right[0]
        y2 = top_right[1]

        slope = (y2 - y1) / (x2 - x1)
        intercept = y1 - slope * x1

        return slope, intercept

    # all content in a line
    curr_line_content = []

    # all lines in a receipt
    receipt_lines = []
    
    """
    line looks like:
        [
            [[x1, y1], [x2, y2], [x3, y3], [x4, y4]], (text, confidence)
        ]
    [top-left, top-right, bottom-right, bottom-left]
    """
    # going from bottom --> top seems to work better
    ocr_output = list(reversed(ocr_output))

    curr_top_slope, curr_top_intercept = calculate_top_slope_and_intercept(ocr_output[0][0])

    for line in ocr_output:
       
        bounding_box = line[0]
        pred = line[1]
        text, confidence = pred

        bb_slope, bb_intercept = calculate_top_slope_and_intercept(bounding_box)

        bb_middle_x = (bounding_box[0][0] + bounding_box[1][0]) / 2
        bb_middle_y = (bounding_box[0][1] + bounding_box[1][1]) / 2

        pred_y_val = curr_top_slope*bb_middle_x + curr_top_intercept


        difference = abs(bb_middle_y - pred_y_val)
        
        if difference > epsilon:
            # we are on a new line
            receipt_lines.append(curr_line_content)

            # reset line info
            curr_line_content = []
            curr_top_intercept = bb_intercept
            curr_top_slope = bb_slope
            curr_line_content.append(text)
        else:
            curr_line_content.append(text)
    
    receipt_lines.append(curr_line_content) 

    return receipt_lines

''' 
    Parsing item name and price (including total and subtotal)
    Assumptions: 
     - prices are on the right of a receipt and are first in a receipt line
     - no non-alphabetic character in item names
'''
def trim_non_numeric(s):
    return re.sub(r"^\D+|\D+$", "", s)

def count_alpha(s):
    return len(re.findall(r"[a-zA-Z]", s))

def extract_price(element):
    price_pattern = r"\d{1,3}(?:[.,]\d{3})*(?:[.,]\d{2})"
    missing_decimal_pattern = r"\d{1,3}(?:\d{3})*(?:\d{2})"
    match_price = re.search(price_pattern, element)
    match_missing_decimal = re.search(missing_decimal_pattern, element)

    if match_price:
        return float(match_price.group())
    elif match_missing_decimal and count_alpha(element) > 2:
        return float(match_missing_decimal.group()) / 100
    else:
        return -1

def is_item(element):
    return len(element) > 2 and extract_price(element) < 0 and count_alpha(element) > 3

def single_price_line(line):
    return len(line) == 1 and extract_price(line[0]) > -1

def item_line(line):
    return len(line) > 0 and is_item(line[0])

def valid_receipt_line(line):
    return len(line) == 2 and extract_price(line[0]) > -1 and is_item(line[1])

def is_tax(s, threshold=0.66):
    return bool(difflib.get_close_matches(s.lower(), ["tax"], cutoff=threshold))

def is_extra_info(s, threshold=0.7):
    return bool(difflib.get_close_matches(s.lower(), ["total", "balance", "count", "subtotal", "discount"], cutoff=threshold))

def clean_receipt_lines(receipt_lines):
    print("receipt_lines:", receipt_lines)
    # # Undo reversing
    # receipt_lines = list(reversed(receipt_lines))
    cleaned_receipt = {
        "tax": 0,
        "items": {} # item: price
                    # item: price
    }

    i = 0
    while i < len(receipt_lines):
        line = receipt_lines[i]

        if len(receipt_lines[i]) == 0:
            i += 1
            continue
        
        # If line just contains a price and the next does not have a price, combine
        if i < len(receipt_lines) - 1 and single_price_line(line) and item_line(receipt_lines[i+1]):
            print("combine: ", receipt_lines[i] + receipt_lines[i+1])
            # cleaned_receipt['items'].append(receipt_lines[i] + receipt_lines[i+1])
            # cleaned_receipt['items'][-1][0] = extract_price(line[0])
            cleaned_receipt['items'][receipt_lines[i+1][0]] = extract_price(line[0])
            i += 1
        elif extract_price(line[0]) > -1 and len(line) > 1:
            # cleaned_receipt['items'].append(line)
            # cleaned_receipt['items'][-1][0] = extract_price(line[0])
            cleaned_receipt['items'][line[1]] = extract_price(line[0])
        
        i += 1
    
    print("cleaned lines:", cleaned_receipt['items'])
    print("cleaned receipt:", cleaned_receipt)
    
    # for i in range(len(cleaned_receipt['items'])):
    #     line = cleaned_receipt['items'][i]
    #     if is_tax(line[1]):
    #         cleaned_receipt['tax'] = line[0]
    #         cleaned_receipt['items'].pop(i)
    #         break

    for key, value in cleaned_receipt['items'].items():  # Iterate over a copy to avoid modification issues
        if is_tax(key):  # Assuming `value` is a tuple or list and tax info is in index 1
            cleaned_receipt['tax'] = value  # Store tax value
            del cleaned_receipt['items'][key]  # Remove the item
            break  # Stop after the first match
    
    cleaned_receipt['items'] = {
        key: value for key, value in cleaned_receipt['items'].items() if not is_extra_info(key)
    }    
    
    return cleaned_receipt
    
    # ignore lines that:
    #       have no words
    #       have no numbers
    #       have nothing with ".##" where # is a number
    # first use regex to see if element contains a price
    # see if non-price part of element could potentially be item name (longer than X characters, contains alphabetic characters)
    # {
    #     balance/total:
    #     items: {
    #           [[item name, price], [price, item name], [price, item name]]
    #     }
    # }    

def scan_receipt(receipt_path, debug=False):
    """
    Given a path to a receipt image, return the lines of the receipt.
    receipt_path: path to the receipt image
    debug: if True, save the image with the OCR results drawn on it
    """

    # run OCR model on receipt image
    ocr = PaddleOCR(use_angle_cls=True, lang='en') # download and load model into memory
    # set CLS to False. Won't be able to recognize 180deg-rotated text, but better performance
    result = ocr.ocr(receipt_path, cls=False)
    result = result[0]

    # there was no text detected
    if result is None:
        return []

    # draw result
    from PIL import Image, ImageFont
    image = Image.open(receipt_path).convert('RGB')
    boxes = [line[0] for line in result]
    txts = [line[1][0] for line in result]
    scores = [line[1][1] for line in result]
    im_show = draw_ocr(image, boxes, txts, scores, font_path='Arial.ttf')
    im_show = Image.fromarray(im_show)

    receipt_name = Path(receipt_path).stem

    if debug:
        im_show.save(
            Path("output") / f'ocr-{receipt_name}.jpg'
        )

    receipt_lines = get_receipt_lines(result, image.size[1] * 0.01)
    cleaned_lines = clean_receipt_lines(receipt_lines)

    return cleaned_lines

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--receipt_name", type=str, help="receipt image file name")
    args = parser.parse_args()

    receipt_path = Path("imgs") / args.receipt_name

    print(
        "\n".join([
            str(line) for line in
            scan_receipt(receipt_path=str(receipt_path), debug=True)
        ])
    )