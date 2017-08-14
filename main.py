from MusicGenerator import MusicGenerator
import Helpers as hp


musician = MusicGenerator(hp.Configuration(epochs=300, train_log_path='./pop4m75h'))
musician.train('./training_songs/Pop')
music = musician.generate(3200, './training_songs/Pop/I_Kissed_A_Girl_-_Chorus.mid',
                          './generated_music', 'pop4m75h')
