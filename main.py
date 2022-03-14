from json import load
from hydrogen_model.hydrogen_v33fuelstationsubsidy import build_h2_model
from data.generate_outputs import main as generate_outputs

def main():
    inputs = load(open('data/inputs/data.json'))
    m = build_h2_model(inputs)
    generate_outputs(m, location='data/outputs/',option='csv')
    
if __name__ == '__main__':
    main()
    
