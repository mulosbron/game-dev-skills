"""
Aestra: The Last Wish - Audio & SFX Synthesis Engine
Synthesizes 35 game-ready 16-bit / 2.5D sound effects (.wav) and 3 ambient music loops (.wav)
along with Godot 4 AudioStreamWAV .import configuration files.
"""

import os
import sys
import math
import wave
import struct
import hashlib
from pathlib import Path
import numpy as np
import scipy.signal as signal

SAMPLE_RATE = 44100

# ==============================================================================
# 1. CORE DSP UTILITIES
# ==============================================================================

def to_16bit_pcm(data: np.ndarray, peak: float = 0.92) -> bytes:
    """Normalizes and converts float array (-1.0 to 1.0) to 16-bit signed PCM bytes."""
    data = np.nan_to_num(data)
    max_val = np.max(np.abs(data))
    if max_val > 1e-6:
        data = (data / max_val) * peak
    else:
        data = np.zeros_like(data)
    
    data = np.clip(data, -1.0, 1.0)
    int_data = (data * 32767.0).astype(np.int16)
    return int_data.tobytes()

def save_wav_file(path: Path, samples: np.ndarray, channels: int = 1, sample_rate: int = SAMPLE_RATE):
    """Saves float samples as standard 16-bit PCM WAV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if channels == 1:
        if samples.ndim > 1:
            samples = samples.flatten()
        raw_bytes = to_16bit_pcm(samples)
    else:
        if samples.shape[0] == 2 and samples.shape[1] != 2:
            left = samples[0]
            right = samples[1]
        else:
            left = samples[:, 0]
            right = samples[:, 1]
        
        max_val = max(np.max(np.abs(left)), np.max(np.abs(right)), 1e-6)
        left = np.clip((left / max_val) * 0.92, -1.0, 1.0)
        right = np.clip((right / max_val) * 0.92, -1.0, 1.0)
        
        interleaved = np.empty((len(left) * 2,), dtype=np.int16)
        interleaved[0::2] = (left * 32767.0).astype(np.int16)
        interleaved[1::2] = (right * 32767.0).astype(np.int16)
        raw_bytes = interleaved.tobytes()

    with wave.open(str(path), 'wb') as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2) # 16-bit
        wf.setframerate(sample_rate)
        wf.writeframes(raw_bytes)

def generate_godot_import(wav_path: Path, is_loop: bool = False):
    """Generates standard Godot 4 .import file for AudioStreamWAV."""
    import_path = wav_path.with_name(wav_path.name + ".import")
    
    rel_path = wav_path.as_posix()
    if "projects/nos/" in rel_path:
        rel_res = "res://" + rel_path.split("projects/nos/")[1]
    else:
        rel_res = f"res://assets/audio/{'music' if is_loop else 'sfx'}/{wav_path.name}"

    md5_hash = hashlib.md5(rel_res.encode('utf-8')).hexdigest()
    uid_hash = md5_hash[:13]
    
    loop_mode = 1 if is_loop else 0  # 1 = Forward loop, 0 = Disabled
    
    content = f"""[remap]

importer="wav"
type="AudioStreamWAV"
uid="uid://{uid_hash}"
path="res://.godot/imported/{wav_path.name}-{md5_hash}.sample"

[deps]

source_file="{rel_res}"
dest_files=["res://.godot/imported/{wav_path.name}-{md5_hash}.sample"]

[params]

force/8_bit=false
force/mono=false
force/max_rate=false
force/max_rate_hz=44100
edit/trim=false
edit/normalize=false
edit/loop_mode={loop_mode}
edit/loop_begin=0
edit/loop_end=-1
compress/mode=0
"""
    import_path.write_text(content, encoding='utf-8')

def butter_filter(data, cutoff, btype='low', order=2):
    nyq = 0.5 * SAMPLE_RATE
    if isinstance(cutoff, (list, tuple)):
        normal_cutoff = [c / nyq for c in cutoff]
        normal_cutoff[0] = max(0.001, min(0.999, normal_cutoff[0]))
        normal_cutoff[1] = max(0.001, min(0.999, normal_cutoff[1]))
    else:
        normal_cutoff = max(0.001, min(0.999, cutoff / nyq))
    b, a = signal.butter(order, normal_cutoff, btype=btype, analog=False)
    return signal.lfilter(b, a, data)

def white_noise(n_samples):
    return np.random.uniform(-1.0, 1.0, n_samples)

def pink_noise(n_samples):
    white = np.random.randn(n_samples)
    fft = np.fft.rfft(white)
    frequencies = np.fft.rfftfreq(n_samples)
    frequencies[0] = 1.0
    s = 1.0 / np.sqrt(frequencies)
    s[0] = 0.0
    fft = fft * s
    pink = np.fft.irfft(fft, n=n_samples)
    return pink / (np.max(np.abs(pink)) + 1e-9)

def brown_noise(n_samples):
    white = np.random.randn(n_samples)
    brown = np.cumsum(white)
    brown = brown / (np.max(np.abs(brown)) + 1e-9)
    return butter_filter(brown, 30, btype='high')

def adsr_env(n_samples, a_len, d_len, s_lvl, r_len):
    a_s = int(a_len * SAMPLE_RATE)
    d_s = int(d_len * SAMPLE_RATE)
    r_s = int(r_len * SAMPLE_RATE)
    s_s = max(0, n_samples - a_s - d_s - r_s)
    
    parts = []
    if a_s > 0:
        parts.append(np.linspace(0.0, 1.0, a_s, endpoint=False))
    if d_s > 0:
        parts.append(np.linspace(1.0, s_lvl, d_s, endpoint=False))
    if s_s > 0:
        parts.append(np.full(s_s, s_lvl))
    if r_s > 0:
        parts.append(np.linspace(s_lvl, 0.0, r_s, endpoint=True))
        
    env = np.concatenate(parts)
    if len(env) < n_samples:
        env = np.pad(env, (0, n_samples - len(env)))
    else:
        env = env[:n_samples]
    return env

def exp_decay_env(n_samples, rate=8.0):
    t = np.linspace(0, 1, n_samples)
    return np.exp(-rate * t)

def soft_clip(x, drive=1.5):
    return np.tanh(drive * x) / np.tanh(drive)

def simple_reverb(samples, delay_ms=45, feedback=0.45, wet=0.25):
    delay_samples = int((delay_ms / 1000.0) * SAMPLE_RATE)
    out = np.copy(samples)
    for i in range(delay_samples, len(samples)):
        out[i] += out[i - delay_samples] * feedback
    return (1.0 - wet) * samples + wet * out

def stereo_reverb(left, right, delay_ms=40, feedback=0.4, wet=0.25):
    l_rev = simple_reverb(left, delay_ms=delay_ms, feedback=feedback, wet=wet)
    r_rev = simple_reverb(right, delay_ms=delay_ms + 13, feedback=feedback * 0.9, wet=wet)
    return l_rev, r_rev

def karplus_strong(freq, duration_sec, decay=0.985, damping=0.5):
    n_samples = int(duration_sec * SAMPLE_RATE)
    period = int(SAMPLE_RATE / max(20.0, freq))
    if period < 2:
        period = 2
    
    buffer = np.random.uniform(-1.0, 1.0, period)
    out = np.zeros(n_samples)
    
    prev = 0.0
    for i in range(n_samples):
        idx = i % period
        val = buffer[idx]
        out[i] = val
        new_val = (val * (1.0 - damping) + prev * damping) * decay
        buffer[idx] = new_val
        prev = new_val
        
    return out

def fm_tone(freq, mod_freq, mod_index, duration_sec, env=None):
    n_samples = int(duration_sec * SAMPLE_RATE)
    t = np.linspace(0, duration_sec, n_samples, endpoint=False)
    modulator = np.sin(2 * np.pi * mod_freq * t) * mod_index
    carrier = np.sin(2 * np.pi * freq * t + modulator)
    if env is not None:
        carrier *= env[:n_samples]
    return carrier

# ==============================================================================
# 2. COMBAT & WEAPON SFX (A)
# ==============================================================================

def syn_sword_slash_light():
    dur = 0.3
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Sweeping bandpass noise
    noise = white_noise(n)
    cf = np.geomspace(2800, 600, n)
    # Block-wise filter simulation for dynamic cutoff
    chunk = 512
    filtered = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        low = max(100, mid_f * 0.6)
        high = min(SAMPLE_RATE * 0.45, mid_f * 1.5)
        filtered[i:c_end] = butter_filter(noise[i:c_end], [low, high], btype='bandpass')
        
    env = adsr_env(n, 0.02, 0.12, 0.1, 0.16)
    whoosh = filtered * env
    
    # Crisp steel shine
    sheen = np.sin(2 * np.pi * 3200 * t) * np.exp(-22 * t) + 0.5 * np.sin(2 * np.pi * 4800 * t) * np.exp(-30 * t)
    
    out = whoosh * 0.7 + sheen * 0.35
    return soft_clip(out, 1.4)

def syn_sword_slash_heavy():
    dur = 0.48
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Low-mid cleave whoosh
    noise = brown_noise(n) + 0.5 * pink_noise(n)
    cf = np.geomspace(1100, 220, n)
    chunk = 512
    filtered = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        low = max(60, mid_f * 0.5)
        high = min(SAMPLE_RATE * 0.45, mid_f * 1.8)
        filtered[i:c_end] = butter_filter(noise[i:c_end], [low, high], btype='bandpass')
        
    env = adsr_env(n, 0.04, 0.2, 0.15, 0.24)
    whoosh = filtered * env
    
    # Sub pitch drop
    sub_f = np.geomspace(180, 50, n)
    sub = np.sin(2 * np.pi * np.cumsum(sub_f) / SAMPLE_RATE) * exp_decay_env(n, 7.0)
    
    # Steel resonant harmonics
    steel = (np.sin(2 * np.pi * 650 * t) + 0.6 * np.sin(2 * np.pi * 1300 * t)) * exp_decay_env(n, 12.0)
    
    out = whoosh * 0.65 + sub * 0.4 + steel * 0.2
    return soft_clip(out, 1.6)

def syn_sword_slash_crit():
    dur = 0.58
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Razor slice transient
    noise = white_noise(n)
    slice_flt = butter_filter(noise, [1800, 7500], btype='bandpass') * adsr_env(n, 0.01, 0.08, 0.05, 0.1)
    
    # High pitch resonant slice (D#7 = 2489Hz, A#7 = 3729Hz, D#8 = 4978Hz)
    vib = 1.0 + 0.015 * np.sin(2 * np.pi * 7 * t)
    ping1 = np.sin(2 * np.pi * 2489 * t * vib) * exp_decay_env(n, 5.0)
    ping2 = 0.6 * np.sin(2 * np.pi * 3729 * t * vib) * exp_decay_env(n, 7.5)
    ping3 = 0.3 * np.sin(2 * np.pi * 4978 * t) * exp_decay_env(n, 11.0)
    crystal = ping1 + ping2 + ping3
    
    # Body whoosh
    whoosh = butter_filter(pink_noise(n), [400, 2200], btype='bandpass') * adsr_env(n, 0.02, 0.15, 0.1, 0.2)
    
    out = slice_flt * 0.5 + crystal * 0.45 + whoosh * 0.3
    return simple_reverb(soft_clip(out, 1.3), delay_ms=30, feedback=0.35, wet=0.2)

def syn_bow_draw():
    dur = 0.45
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Wood creaks (train of micro bursts)
    clicks = np.zeros(n)
    step_indices = np.random.choice(range(int(0.05 * n), int(0.9 * n)), 18, replace=False)
    for idx in step_indices:
        span = min(300, n - idx)
        clicks[idx:idx+span] += np.random.uniform(-1, 1, span) * np.linspace(1, 0, span)
    clicks = butter_filter(clicks, [400, 2400], btype='bandpass')
    
    # Taught bowstring tension rising tone
    f_curve = np.linspace(120, 280, n)
    tone = np.sin(2 * np.pi * np.cumsum(f_curve) / SAMPLE_RATE) * adsr_env(n, 0.2, 0.1, 0.8, 0.15)
    
    out = clicks * 0.7 + tone * 0.3
    return soft_clip(out, 1.2)

def syn_arrow_shoot():
    dur = 0.26
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Plucked string release twang
    string = karplus_strong(340, dur, decay=0.96, damping=0.45)
    
    # Air zip
    noise = white_noise(n)
    cf = np.geomspace(3400, 800, n)
    chunk = 256
    zip_air = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        zip_air[i:c_end] = butter_filter(noise[i:c_end], [max(100, mid_f*0.7), min(SAMPLE_RATE*0.45, mid_f*1.4)], btype='bandpass')
    zip_air *= adsr_env(n, 0.01, 0.08, 0.05, 0.12)
    
    out = string * 0.55 + zip_air * 0.45
    return soft_clip(out, 1.4)

def syn_arrow_impact():
    dur = 0.32
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Thud
    sub_f = np.geomspace(170, 50, n)
    thud = np.sin(2 * np.pi * np.cumsum(sub_f) / SAMPLE_RATE) * exp_decay_env(n, 16.0)
    
    # Splinter crack
    splinter = butter_filter(white_noise(n), [800, 3600], btype='bandpass') * exp_decay_env(n, 32.0)
    
    # Arrow shaft shudder
    shudder = np.sin(2 * np.pi * 210 * t) * exp_decay_env(n, 10.0)
    
    out = thud * 0.6 + splinter * 0.5 + shudder * 0.25
    return soft_clip(out, 1.5)

def syn_shield_block():
    dur = 0.65
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Modal iron frequencies
    partials = [430, 895, 1420, 2180, 3250]
    weights = [0.45, 0.35, 0.25, 0.18, 0.1]
    rates = [7.0, 9.0, 11.0, 14.0, 18.0]
    
    bell = np.zeros(n)
    for p, w, r in zip(partials, weights, rates):
        bell += w * np.sin(2 * np.pi * p * t) * exp_decay_env(n, r)
        
    # Heavy transient impact
    thud = butter_filter(white_noise(n), 350, btype='low') * exp_decay_env(n, 25.0)
    click = butter_filter(white_noise(n), [1500, 6000], btype='bandpass') * exp_decay_env(n, 60.0)
    
    out = bell * 0.6 + thud * 0.4 + click * 0.35
    return simple_reverb(soft_clip(out, 1.4), delay_ms=35, feedback=0.4, wet=0.22)

# ==============================================================================
# 3. MAGIC & ELEMENTAL SFX (B)
# ==============================================================================

def syn_fire_cast():
    dur = 0.55
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Spark ignition transient
    spark_noise = butter_filter(white_noise(n), [2000, 8000], btype='bandpass') * adsr_env(n, 0.01, 0.05, 0.0, 0.05)
    
    # Whoosh blaze
    blaze = pink_noise(n)
    cf = np.concatenate([np.linspace(350, 1900, n//3), np.linspace(1900, 300, n - n//3)])
    chunk = 512
    flt_blaze = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        flt_blaze[i:c_end] = butter_filter(blaze[i:c_end], [max(60, mid_f*0.6), min(SAMPLE_RATE*0.45, mid_f*1.6)], btype='bandpass')
    flt_blaze *= adsr_env(n, 0.04, 0.15, 0.3, 0.25)
    
    # Random crackles
    crackles = np.zeros(n)
    sparks = np.random.choice(range(int(0.08 * n), int(0.7 * n)), 12, replace=False)
    for idx in sparks:
        crackles[idx:min(n, idx+150)] += np.random.uniform(-1, 1, min(150, n - idx)) * 0.8
    crackles = butter_filter(crackles, 3000, btype='high')
    
    out = spark_noise * 0.4 + flt_blaze * 0.6 + crackles * 0.35
    return soft_clip(out, 1.3)

def syn_fire_ring_roar():
    dur = 1.35
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Deep resonant expanding blaze with tremolo flutter
    noise = brown_noise(n) + pink_noise(n)
    flt = butter_filter(noise, [100, 650], btype='bandpass')
    flutter = 1.0 + 0.35 * np.sin(2 * np.pi * 8.5 * t)
    roar = flt * flutter * adsr_env(n, 0.15, 0.3, 0.5, 0.5)
    
    # Sub rumble
    sub = np.sin(2 * np.pi * 55 * t) * adsr_env(n, 0.1, 0.3, 0.4, 0.4)
    
    # Ember crackle bed
    embers = np.zeros(n)
    pops = np.random.choice(range(int(0.1 * n), int(0.9 * n)), 45, replace=False)
    for idx in pops:
        span = min(200, n - idx)
        embers[idx:idx+span] += np.random.uniform(-1, 1, span) * np.linspace(1, 0, span)
    embers = butter_filter(embers, 2500, btype='high')
    
    out = roar * 0.6 + sub * 0.35 + embers * 0.3
    return simple_reverb(soft_clip(out, 1.4), delay_ms=50, feedback=0.45, wet=0.25)

def syn_water_splash():
    dur = 0.72
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Hydro surge noise sweep
    noise = white_noise(n)
    cf = np.geomspace(1600, 350, n)
    chunk = 512
    surge = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        surge[i:c_end] = butter_filter(noise[i:c_end], [max(60, mid_f*0.6), min(SAMPLE_RATE*0.45, mid_f*1.5)], btype='bandpass')
    surge *= adsr_env(n, 0.02, 0.18, 0.2, 0.35)
    
    # Liquid droplets (fast pitch chirps)
    droplets = np.zeros(n)
    drop_times = [0.06, 0.12, 0.18, 0.25, 0.33, 0.42]
    drop_freqs = [(600, 1100), (800, 1400), (950, 1600), (700, 1250), (1100, 1800), (850, 1350)]
    for dt, (f_start, f_end) in zip(drop_times, drop_freqs):
        idx = int(dt * SAMPLE_RATE)
        span = int(0.045 * SAMPLE_RATE)
        if idx + span < n:
            t_span = np.linspace(0, 0.045, span)
            f_chirp = np.linspace(f_start, f_end, span)
            drop_sig = np.sin(2 * np.pi * np.cumsum(f_chirp) / SAMPLE_RATE) * np.sin(np.pi * np.linspace(0, 1, span))
            droplets[idx:idx+span] += drop_sig * 0.4
            
    out = surge * 0.6 + droplets * 0.45
    return simple_reverb(soft_clip(out, 1.2), delay_ms=35, feedback=0.35, wet=0.2)

def syn_ice_freeze():
    dur = 0.75
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Exponentially dense crystallizing crackles
    crackle = np.zeros(n)
    density_curve = (np.linspace(0, 1, n) ** 1.8)
    rand_vals = np.random.uniform(0, 1, n)
    crackle_pts = np.where(rand_vals < (0.015 + 0.12 * density_curve))[0]
    for idx in crackle_pts:
        span = min(80, n - idx)
        crackle[idx:idx+span] += np.random.uniform(-1, 1, span) * np.linspace(1, 0, span)
    crackle = butter_filter(crackle, [3500, 12000], btype='bandpass')
    
    # High crystalline tones (C6, E6, G6, C7)
    tones = [1046, 1318, 1568, 2093]
    crystal = np.zeros(n)
    for freq in tones:
        crystal += np.sin(2 * np.pi * freq * t) * (0.8 + 0.2 * np.sin(2 * np.pi * 12 * t))
    crystal *= adsr_env(n, 0.1, 0.25, 0.4, 0.3)
    
    out = crackle * 0.6 + crystal * 0.35
    return simple_reverb(soft_clip(out, 1.3), delay_ms=40, feedback=0.4, wet=0.25)

def syn_frost_shatter():
    dur = 0.82
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Glassy explosive crash transient
    crash = butter_filter(white_noise(n), 2800, btype='high') * exp_decay_env(n, 12.0)
    
    # Punchy cold impact
    thump = np.sin(2 * np.pi * np.geomspace(220, 60, n) * t) * exp_decay_env(n, 22.0)
    
    # Descending crystalline ice shard pings
    shards = np.zeros(n)
    shard_freqs = [5600, 4800, 4200, 3600, 3100, 2700, 2300, 1950, 1600, 1350]
    for i, freq in enumerate(shard_freqs):
        offset = int((0.02 + i * 0.04) * SAMPLE_RATE)
        span = int(0.18 * SAMPLE_RATE)
        if offset + span < n:
            t_s = np.linspace(0, 0.18, span)
            ping = np.sin(2 * np.pi * freq * t_s) * np.exp(-18 * t_s)
            shards[offset:offset+span] += ping * 0.25
            
    out = crash * 0.5 + thump * 0.4 + shards * 0.5
    return simple_reverb(soft_clip(out, 1.35), delay_ms=30, feedback=0.35, wet=0.22)

def syn_steam_hiss():
    dur = 0.78
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Hot vaporization sizzle
    noise = white_noise(n)
    hiss = butter_filter(noise, [3600, 14000], btype='bandpass')
    env = adsr_env(n, 0.015, 0.12, 0.35, 0.45)
    
    # Boiling undertone flutter
    boil = butter_filter(noise, [250, 700], btype='bandpass') * (1.0 + 0.4 * np.sin(2 * np.pi * 14 * t)) * env
    
    out = hiss * 0.7 * env + boil * 0.3
    return soft_clip(out, 1.2)

def syn_magic_orb_shoot():
    dur = 0.42
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Pitch bend curve: 420 -> 920 -> 320 Hz
    f_curve = np.concatenate([np.linspace(420, 920, n//2), np.geomspace(920, 320, n - n//2)])
    phase = 2 * np.pi * np.cumsum(f_curve) / SAMPLE_RATE
    
    # FM modulation for mystic buzzing zap
    mod_phase = 2 * np.pi * 140 * t
    mod_index = np.linspace(4.5, 0.8, n)
    orb = np.sin(phase + mod_index * np.sin(mod_phase))
    
    env = adsr_env(n, 0.01, 0.1, 0.3, 0.18)
    sparkle = butter_filter(white_noise(n), [4000, 9000], btype='bandpass') * exp_decay_env(n, 14.0)
    
    out = orb * env * 0.75 + sparkle * 0.25
    return simple_reverb(soft_clip(out, 1.3), delay_ms=25, feedback=0.3, wet=0.18)

# ==============================================================================
# 4. IMPACTS, HIT-STOPS & MONSTERS (C)
# ==============================================================================

def syn_hit_punchy():
    dur = 0.28
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Sub pitch drop
    sub_f = np.geomspace(220, 48, n)
    sub = np.sin(2 * np.pi * np.cumsum(sub_f) / SAMPLE_RATE) * exp_decay_env(n, 18.0)
    
    # Mid crack transient
    crack = butter_filter(white_noise(n), [650, 2400], btype='bandpass') * exp_decay_env(n, 35.0)
    
    # High slap transient
    slap = butter_filter(white_noise(n), 3000, btype='high') * exp_decay_env(n, 70.0)
    
    out = sub * 0.6 + crack * 0.45 + slap * 0.35
    return soft_clip(out, 1.8)

def syn_hit_stomp_aoe():
    dur = 0.95
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Massive sub-bass impact (GDD 3.3 mass kill stomp)
    sub_f = np.geomspace(85, 32, n)
    sub = np.sin(2 * np.pi * np.cumsum(sub_f) / SAMPLE_RATE) * adsr_env(n, 0.005, 0.18, 0.3, 0.5)
    
    # Multi-transient bone crush / flesh splatter
    crush = butter_filter(brown_noise(n) + white_noise(n), [150, 1800], btype='bandpass') * exp_decay_env(n, 9.0)
    
    # Ground shudder rumble
    shudder = np.sin(2 * np.pi * 48 * t) * (1.0 + 0.3 * np.sin(2 * np.pi * 9 * t)) * exp_decay_env(n, 5.0)
    
    out = sub * 0.55 + crush * 0.5 + shudder * 0.3
    return simple_reverb(soft_clip(out, 1.7), delay_ms=45, feedback=0.45, wet=0.25)

def syn_imp_groan():
    dur = 0.65
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Pitch bend for snarling screech
    f_curve = np.concatenate([np.linspace(480, 640, n//3), np.geomspace(640, 260, n - n//3)])
    phase = 2 * np.pi * np.cumsum(f_curve) / SAMPLE_RATE
    saw = 2.0 * (phase / (2 * np.pi) - np.floor(phase / (2 * np.pi) + 0.5))
    
    # Formant filter (vowel screech)
    f_imp = butter_filter(saw, [700, 2400], btype='bandpass')
    
    # Ring modulation for gutter snarl
    ring = np.sin(2 * np.pi * 85 * t)
    snarl = f_imp * (0.6 + 0.4 * ring)
    
    # Raspy throat hiss
    hiss = butter_filter(white_noise(n), [1200, 4500], btype='bandpass') * adsr_env(n, 0.05, 0.2, 0.3, 0.2)
    
    env = adsr_env(n, 0.04, 0.15, 0.4, 0.3)
    out = (snarl * 0.65 + hiss * 0.35) * env
    return simple_reverb(soft_clip(out, 1.5), delay_ms=30, feedback=0.35, wet=0.2)

def syn_boss_roar():
    dur = 1.65
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Dual detuned low saws + sub
    f1 = np.concatenate([np.linspace(62, 78, n//3), np.geomspace(78, 42, n - n//3)])
    phase1 = 2 * np.pi * np.cumsum(f1) / SAMPLE_RATE
    phase2 = 2 * np.pi * np.cumsum(f1 * 1.015) / SAMPLE_RATE
    
    saw1 = 2.0 * (phase1 / (2 * np.pi) - np.floor(phase1 / (2 * np.pi) + 0.5))
    saw2 = 2.0 * (phase2 / (2 * np.pi) - np.floor(phase2 / (2 * np.pi) + 0.5))
    sub = np.sin(phase1 * 0.5)
    
    raw = saw1 * 0.4 + saw2 * 0.4 + sub * 0.4
    
    # Sweeping vowel formant filter (A -> O -> U)
    cf = np.concatenate([np.linspace(950, 1200, n//3), np.geomspace(1200, 320, n - n//3)])
    chunk = 512
    flt_roar = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        flt_roar[i:c_end] = butter_filter(raw[i:c_end], [max(40, mid_f*0.45), min(SAMPLE_RATE*0.45, mid_f*1.6)], btype='bandpass')
        
    # Throat AM flutter
    trem = 1.0 + 0.4 * np.sin(2 * np.pi * 11 * t)
    flt_roar *= trem
    
    env = adsr_env(n, 0.12, 0.3, 0.65, 0.45)
    roar = flt_roar * env
    
    # Cavernous roar breath
    breath = butter_filter(brown_noise(n), [80, 800], btype='bandpass') * env
    
    out = roar * 0.7 + breath * 0.35
    return simple_reverb(soft_clip(out, 1.8), delay_ms=65, feedback=0.55, wet=0.3)

def syn_monster_death_dissolve():
    dur = 1.15
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Descending dark dust whisper
    noise = pink_noise(n)
    cf = np.geomspace(1800, 160, n)
    chunk = 512
    dust = np.zeros(n)
    for i in range(0, n, chunk):
        c_end = min(i + chunk, n)
        mid_f = cf[(i + c_end) // 2]
        dust[i:c_end] = butter_filter(noise[i:c_end], [max(40, mid_f*0.5), min(SAMPLE_RATE*0.45, mid_f*1.7)], btype='bandpass')
    dust *= exp_decay_env(n, 4.5)
    
    # Eerie minor harmonic whisper (A2, C3, E3, G#3)
    eerie = (np.sin(2 * np.pi * 110 * t) + 0.7 * np.sin(2 * np.pi * 130.8 * t) + 0.5 * np.sin(2 * np.pi * 164.8 * t) + 0.3 * np.sin(2 * np.pi * 207.6 * t))
    eerie *= (1.0 + 0.3 * np.sin(2 * np.pi * 5.5 * t)) * exp_decay_env(n, 5.0)
    
    out = dust * 0.6 + eerie * 0.4
    return simple_reverb(soft_clip(out, 1.2), delay_ms=45, feedback=0.45, wet=0.25)

# ==============================================================================
# 5. LOOT, ECONOMY & PROGRESSION (D)
# ==============================================================================

def syn_gold_pickup():
    dur = 0.32
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Two crisp bell pings (B6 = 1975Hz, E7 = 2637Hz)
    ping1 = np.sin(2 * np.pi * 1975 * t) * exp_decay_env(n, 22.0)
    
    # Second ping offset by 35ms
    offset = int(0.035 * SAMPLE_RATE)
    ping2 = np.zeros(n)
    t2 = np.linspace(0, dur - 0.035, n - offset)
    ping2[offset:] = (np.sin(2 * np.pi * 2637 * t2) + 0.35 * np.sin(2 * np.pi * 5274 * t2)) * exp_decay_env(n - offset, 18.0)
    
    # Coin sparkle
    sparkle = butter_filter(white_noise(n), 4500, btype='high') * exp_decay_env(n, 35.0)
    
    out = ping1 * 0.45 + ping2 * 0.55 + sparkle * 0.15
    return soft_clip(out, 1.2)

def syn_loot_drop_common():
    dur = 0.28
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Subtle wooden/leather thud + bounce
    thud = np.sin(2 * np.pi * np.geomspace(140, 50, n) * t) * exp_decay_env(n, 20.0)
    click = butter_filter(white_noise(n), [400, 1800], btype='bandpass') * exp_decay_env(n, 35.0)
    
    # Gentle bounce tap
    offset = int(0.06 * SAMPLE_RATE)
    bounce = np.zeros(n)
    if offset < n:
        b_len = n - offset
        bounce[offset:] = np.sin(2 * np.pi * 110 * np.linspace(0, (b_len)/SAMPLE_RATE, b_len)) * exp_decay_env(b_len, 28.0) * 0.35
        
    out = thud * 0.6 + click * 0.4 + bounce
    return soft_clip(out, 1.2)

def syn_loot_drop_rare():
    dur = 0.85
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # 3 ascending crystal tones (E6 = 1318Hz, G#6 = 1661Hz, B6 = 1975Hz)
    chimes = [1318, 1661, 1975]
    out = np.zeros(n)
    for i, freq in enumerate(chimes):
        offset = int(i * 0.06 * SAMPLE_RATE)
        span = n - offset
        t_span = np.linspace(0, span / SAMPLE_RATE, span)
        tone = (np.sin(2 * np.pi * freq * t_span) + 0.25 * np.sin(2 * np.pi * freq * 2 * t_span)) * exp_decay_env(span, 7.0)
        out[offset:] += tone * 0.35
        
    # Shimmering tremolo tail
    shimmer = butter_filter(white_noise(n), [3500, 9000], btype='bandpass') * exp_decay_env(n, 9.0) * (1.0 + 0.4 * np.sin(2 * np.pi * 9 * t))
    out += shimmer * 0.2
    
    return simple_reverb(soft_clip(out, 1.2), delay_ms=35, feedback=0.4, wet=0.22)

def syn_loot_drop_unique():
    dur = 1.45
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Epic golden fanfare beam chime (C6, E6, G6, B6, D7, G7)
    notes = [1046, 1318, 1568, 1975, 2349, 3136]
    arpeggio = np.zeros(n)
    for i, freq in enumerate(notes):
        offset = int(i * 0.045 * SAMPLE_RATE)
        span = n - offset
        t_s = np.linspace(0, span / SAMPLE_RATE, span)
        tone = (np.sin(2 * np.pi * freq * t_s) + 0.3 * np.sin(2 * np.pi * freq * 2 * t_s)) * exp_decay_env(span, 5.5)
        arpeggio[offset:] += tone * 0.3
        
    # Celestial pad swell
    pad = (np.sin(2 * np.pi * 261.6 * t) + 0.7 * np.sin(2 * np.pi * 329.6 * t) + 0.6 * np.sin(2 * np.pi * 392.0 * t)) * adsr_env(n, 0.1, 0.3, 0.5, 0.5)
    
    # Golden beam bass foundation
    bass = np.sin(2 * np.pi * 130.8 * t) * adsr_env(n, 0.05, 0.2, 0.4, 0.6)
    
    out = arpeggio * 0.6 + pad * 0.25 + bass * 0.25
    return simple_reverb(soft_clip(out, 1.3), delay_ms=50, feedback=0.5, wet=0.28)

def syn_level_up():
    dur = 1.85
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Ascending RPG fanfare sequence: C5, E5, G5, C6, D6, E6, G6
    notes = [523, 659, 784, 1046, 1175, 1318, 1568]
    fanfare = np.zeros(n)
    step = 0.09
    for i, freq in enumerate(notes):
        offset = int(i * step * SAMPLE_RATE)
        span = n - offset
        t_s = np.linspace(0, span / SAMPLE_RATE, span)
        # Synth brass/bell harmonics
        harmonics = np.sin(2 * np.pi * freq * t_s) + 0.45 * np.sin(2 * np.pi * freq * 2 * t_s) + 0.2 * np.sin(2 * np.pi * freq * 3 * t_s)
        decay = 4.0 if i == len(notes) - 1 else 9.0
        fanfare[offset:] += harmonics * exp_decay_env(span, decay) * (0.35 if i < len(notes)-1 else 0.55)
        
    # Triumphant major chord bed on the resolution
    res_offset = int(len(notes) * step * SAMPLE_RATE)
    res_chord = np.zeros(n)
    if res_offset < n:
        res_span = n - res_offset
        t_res = np.linspace(0, res_span / SAMPLE_RATE, res_span)
        chord = np.sin(2 * np.pi * 523 * t_res) + 0.8 * np.sin(2 * np.pi * 659 * t_res) + 0.7 * np.sin(2 * np.pi * 784 * t_res) + 0.5 * np.sin(2 * np.pi * 1046 * t_res)
        res_chord[res_offset:] = chord * adsr_env(res_span, 0.05, 0.2, 0.6, 0.5) * 0.35
        
    out = fanfare * 0.7 + res_chord * 0.35
    return simple_reverb(soft_clip(out, 1.3), delay_ms=45, feedback=0.45, wet=0.25)

def syn_craft_hammer():
    dur = 0.58
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Ringing anvil resonance (1480, 2960, 4440 Hz)
    anvil = (np.sin(2 * np.pi * 1480 * t) * exp_decay_env(n, 9.0) +
             0.5 * np.sin(2 * np.pi * 2960 * t) * exp_decay_env(n, 14.0) +
             0.25 * np.sin(2 * np.pi * 4440 * t) * exp_decay_env(n, 20.0))
             
    # Solid heavy hammer head clunk
    thud = np.sin(2 * np.pi * np.geomspace(240, 75, n) * t) * exp_decay_env(n, 22.0)
    transient = butter_filter(white_noise(n), [1000, 5000], btype='bandpass') * exp_decay_env(n, 50.0)
    
    out = anvil * 0.6 + thud * 0.4 + transient * 0.35
    return simple_reverb(soft_clip(out, 1.4), delay_ms=30, feedback=0.35, wet=0.2)

def syn_upgrade_success():
    dur = 1.25
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # +basma success joyful magic surge: rising magic whoosh + 4 major bells (F#5, A#5, C#6, F#6)
    whoosh = butter_filter(pink_noise(n), [300, 2200], btype='bandpass') * adsr_env(n, 0.12, 0.2, 0.1, 0.2)
    
    bells = [740, 932, 1109, 1480]
    chimes = np.zeros(n)
    for i, freq in enumerate(bells):
        offset = int((0.08 + i * 0.06) * SAMPLE_RATE)
        span = n - offset
        t_s = np.linspace(0, span / SAMPLE_RATE, span)
        tone = (np.sin(2 * np.pi * freq * t_s) + 0.3 * np.sin(2 * np.pi * freq * 2 * t_s)) * exp_decay_env(span, 5.0)
        chimes[offset:] += tone * 0.35
        
    sparkles = butter_filter(white_noise(n), 4000, btype='high') * adsr_env(n, 0.1, 0.2, 0.3, 0.4) * (1.0 + 0.5 * np.sin(2 * np.pi * 14 * t))
    
    out = whoosh * 0.3 + chimes * 0.6 + sparkles * 0.25
    return simple_reverb(soft_clip(out, 1.3), delay_ms=45, feedback=0.45, wet=0.25)

def syn_upgrade_fail():
    dur = 0.85
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Sharp fracture crack snap
    snap = butter_filter(white_noise(n), [1200, 6000], btype='bandpass') * exp_decay_env(n, 45.0)
    
    # Steam sizzle
    sizzle = butter_filter(white_noise(n), 3200, btype='high') * adsr_env(n, 0.02, 0.15, 0.3, 0.3)
    
    # Sad descending tritone (A4 = 440Hz -> Eb4 = 311Hz)
    t_half = n // 2
    tritone1 = np.sin(2 * np.pi * 440 * t[:t_half]) * exp_decay_env(t_half, 7.0)
    tritone2 = np.sin(2 * np.pi * 311 * t[:n - t_half]) * exp_decay_env(n - t_half, 6.0)
    tones = np.concatenate([tritone1 * 0.4, tritone2 * 0.45])
    
    out = snap * 0.5 + sizzle * 0.35 + tones * 0.4
    return simple_reverb(soft_clip(out, 1.3), delay_ms=35, feedback=0.35, wet=0.2)

def syn_potion_drink():
    dur = 0.72
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Two resonant liquid glugs
    glugs = np.zeros(n)
    glug_params = [(0.04, 440, 260), (0.22, 510, 310)]
    for dt, f_start, f_end in glug_params:
        idx = int(dt * SAMPLE_RATE)
        span = int(0.09 * SAMPLE_RATE)
        t_g = np.linspace(0, 0.09, span)
        f_c = np.geomspace(f_start, f_end, span)
        phase = 2 * np.pi * np.cumsum(f_c) / SAMPLE_RATE
        env_g = np.sin(np.pi * np.linspace(0, 1, span)) ** 2
        glugs[idx:idx+span] += np.sin(phase) * env_g * 0.55
        
    # Refreshing swallow click
    swallow_idx = int(0.42 * SAMPLE_RATE)
    swallow_span = int(0.06 * SAMPLE_RATE)
    t_sw = np.linspace(0, 0.06, swallow_span)
    glugs[swallow_idx:swallow_idx+swallow_span] += np.sin(2 * np.pi * 180 * t_sw) * np.exp(-30 * t_sw) * 0.35
    
    # Sparkle of health restored
    sparkle = butter_filter(white_noise(n), 4000, btype='high') * adsr_env(n, 0.35, 0.1, 0.2, 0.2)
    tone_heal = (np.sin(2 * np.pi * 1046 * t) + 0.5 * np.sin(2 * np.pi * 1318 * t)) * adsr_env(n, 0.35, 0.1, 0.2, 0.2)
    
    out = glugs * 0.65 + sparkle * 0.2 + tone_heal * 0.25
    return soft_clip(out, 1.2)

# ==============================================================================
# 6. PETS (E)
# ==============================================================================

def syn_pet_turtle_taunt():
    dur = 0.62
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Low subterranean grunt/thud
    f_grunt = np.geomspace(120, 55, n)
    thud = np.sin(2 * np.pi * np.cumsum(f_grunt) / SAMPLE_RATE) * exp_decay_env(n, 12.0)
    
    # Earthy shell scrape resonance
    scrape = butter_filter(brown_noise(n), [70, 320], btype='bandpass') * adsr_env(n, 0.05, 0.15, 0.4, 0.3)
    
    out = thud * 0.65 + scrape * 0.45
    return simple_reverb(soft_clip(out, 1.4), delay_ms=40, feedback=0.4, wet=0.22)

def syn_pet_raven_caw():
    dur = 0.52
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Metallic caw pitch sweep
    f_caw = np.geomspace(740, 440, n)
    phase = 2 * np.pi * np.cumsum(f_caw) / SAMPLE_RATE
    carrier = np.sin(phase) + 0.4 * np.sin(2 * phase)
    
    # Formants at 850Hz and 1950Hz
    caw1 = butter_filter(carrier, [650, 1100], btype='bandpass')
    caw2 = butter_filter(carrier, [1600, 2300], btype='bandpass')
    
    # Raspy throat vibration
    rasp = 1.0 + 0.45 * np.sin(2 * np.pi * 65 * t)
    env = adsr_env(n, 0.02, 0.12, 0.6, 0.25)
    
    out = (caw1 * 0.6 + caw2 * 0.4) * rasp * env
    return simple_reverb(soft_clip(out, 1.3), delay_ms=25, feedback=0.3, wet=0.18)

def syn_pet_fox_bark():
    dur = 0.36
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # High-pitched fox yip/chirp: rapid 720Hz -> 1420Hz -> 580Hz
    n_up = int(0.08 * SAMPLE_RATE)
    n_down = n - n_up
    f_curve = np.concatenate([np.linspace(720, 1420, n_up), np.geomspace(1420, 580, n_down)])
    phase = 2 * np.pi * np.cumsum(f_curve) / SAMPLE_RATE
    
    carrier = np.sin(phase) + 0.35 * np.sin(2 * phase) + 0.15 * np.sin(3 * phase)
    env = adsr_env(n, 0.015, 0.08, 0.4, 0.18)
    
    out = carrier * env
    return simple_reverb(soft_clip(out, 1.3), delay_ms=20, feedback=0.25, wet=0.15)

# ==============================================================================
# 7. UI SFX (F)
# ==============================================================================

def syn_ui_click():
    dur = 0.11
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Clean wooden/metallic tap
    click = butter_filter(white_noise(n), [1400, 7000], btype='bandpass') * exp_decay_env(n, 55.0)
    body = np.sin(2 * np.pi * 580 * t) * exp_decay_env(n, 38.0)
    
    out = click * 0.6 + body * 0.45
    return soft_clip(out, 1.2)

def syn_ui_hover():
    dur = 0.06
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Soft delicate tick
    tone = np.sin(2 * np.pi * 1250 * t) * np.sin(np.pi * np.linspace(0, 1, n))
    return soft_clip(tone * 0.4, 1.0)

def syn_ui_bag_open():
    dur = 0.36
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Series of soft leather friction noise packets
    rustle = np.zeros(n)
    times = [0.02, 0.08, 0.15, 0.22]
    for tm in times:
        idx = int(tm * SAMPLE_RATE)
        span = int(0.06 * SAMPLE_RATE)
        if idx + span < n:
            burst = butter_filter(white_noise(span), [600, 2400], btype='bandpass') * np.sin(np.pi * np.linspace(0, 1, span))
            rustle[idx:idx+span] += burst * 0.45
            
    # Buckle clink
    clink_idx = int(0.12 * SAMPLE_RATE)
    clink_span = int(0.08 * SAMPLE_RATE)
    if clink_idx + clink_span < n:
        t_c = np.linspace(0, 0.08, clink_span)
        clink = np.sin(2 * np.pi * 2200 * t_c) * np.exp(-35 * t_c)
        rustle[clink_idx:clink_idx+clink_span] += clink * 0.3
        
    return soft_clip(rustle, 1.2)

def syn_ui_quest_accept():
    dur = 0.48
    n = int(dur * SAMPLE_RATE)
    t = np.linspace(0, dur, n)
    
    # Sturdy parchment stamp: desk impact + wax seal press
    desk = np.sin(2 * np.pi * np.geomspace(120, 45, n) * t) * exp_decay_env(n, 18.0)
    stamp_transient = butter_filter(white_noise(n), [400, 1800], btype='bandpass') * exp_decay_env(n, 28.0)
    
    # Paper flutter / wax press
    friction = butter_filter(pink_noise(n), [800, 3200], btype='bandpass') * adsr_env(n, 0.04, 0.1, 0.2, 0.2)
    
    out = desk * 0.6 + stamp_transient * 0.45 + friction * 0.25
    return soft_clip(out, 1.3)

# ==============================================================================
# 8. AMBIENT MUSIC STEMS / LOOPS (PROCEDURAL WAVE SYNTHESIS)
# ==============================================================================

def synthesize_music_village_hub():
    """
    Peaceful acoustic lute & flute folk melody in D Major / G Major.
    Duration: 16.0s (seamless loop via circular overlap).
    BPM = 90. 1 beat = 0.6667s. 4 beats/bar = 2.6667s. 6 bars = 16.0s.
    """
    loop_dur = 16.0
    tail_dur = 3.0
    total_dur = loop_dur + tail_dur
    total_samples = int(total_dur * SAMPLE_RATE)
    loop_samples = int(loop_dur * SAMPLE_RATE)
    
    left = np.zeros(total_samples)
    right = np.zeros(total_samples)
    
    beat_sec = 60.0 / 90.0 # 0.6667s
    bar_sec = beat_sec * 4.0 # 2.6667s
    
    # Chords progression (6 bars): D - G - Bm - G - Em - A
    # Frequencies (MIDI notes)
    # D major: D3 (146.8), A3 (220.0), D4 (293.7), F#4 (370.0)
    # G major: G3 (196.0), B3 (246.9), D4 (293.7), G4 (392.0)
    # Bm:      B2 (123.5), F#3 (185.0), B3 (246.9), D4 (293.7)
    # G major: G3, B3, D4, G4
    # Em:      E3 (164.8), B3 (246.9), E4 (329.6), G4 (392.0)
    # A major: A2 (110.0), E3 (164.8), A3 (220.0), C#4 (277.2)
    progression = [
        [146.8, 220.0, 293.7, 370.0], # D
        [196.0, 246.9, 293.7, 392.0], # G
        [123.5, 185.0, 246.9, 293.7], # Bm
        [196.0, 246.9, 293.7, 392.0], # G
        [164.8, 246.9, 329.6, 392.0], # Em
        [110.0, 164.8, 220.0, 277.2], # A
    ]
    
    # 1. Plucked Lute Pattern (Arpeggio rhythm on Karplus-Strong)
    for bar_idx, chord in enumerate(progression):
        bar_start = bar_idx * bar_sec
        # 8 eighth notes per bar
        for beat_step in range(8):
            t_note = bar_start + beat_step * (beat_sec / 2.0)
            if t_note >= loop_dur:
                break
            idx_start = int(t_note * SAMPLE_RATE)
            note_freq = chord[beat_step % len(chord)]
            pluck = karplus_strong(note_freq, 1.2, decay=0.985, damping=0.35)
            n_p = len(pluck)
            if idx_start + n_p > total_samples:
                n_p = total_samples - idx_start
            
            # Alternate stereo panning
            pan = 0.35 if beat_step % 2 == 0 else 0.65
            left[idx_start:idx_start+n_p] += pluck[:n_p] * (1.0 - pan) * 0.25
            right[idx_start:idx_start+n_p] += pluck[:n_p] * pan * 0.25
            
    # 2. Warm Bass (Root notes)
    roots = [73.4, 98.0, 61.7, 98.0, 82.4, 55.0] # D2, G2, B1, G2, E2, A1
    for bar_idx, root_f in enumerate(roots):
        t_bar = bar_idx * bar_sec
        idx_b = int(t_bar * SAMPLE_RATE)
        span_b = int(bar_sec * 0.95 * SAMPLE_RATE)
        if idx_b + span_b > total_samples:
            span_b = total_samples - idx_b
        t_axis = np.linspace(0, span_b / SAMPLE_RATE, span_b)
        bass_wave = np.sin(2 * np.pi * root_f * t_axis) + 0.3 * np.sin(2 * np.pi * root_f * 2 * t_axis)
        env_b = adsr_env(span_b, 0.05, 0.2, 0.7, 0.2)
        left[idx_b:idx_b+span_b] += bass_wave * env_b * 0.28
        right[idx_b:idx_b+span_b] += bass_wave * env_b * 0.28

    # 3. Wooden Folk Flute Melody
    # Pentatonic lyrical phrases: D4, E4, F#4, A4, B4, D5, E5, F#5
    melody_notes = [
        # Bar 1 (D)
        (0.0, 587.3, 1.0), (1.0, 740.0, 0.5), (1.5, 880.0, 1.0),
        # Bar 2 (G)
        (2.67, 987.8, 1.2), (4.0, 880.0, 0.6), (4.67, 740.0, 0.6),
        # Bar 3 (Bm)
        (5.33, 587.3, 1.4), (7.0, 493.9, 0.8),
        # Bar 4 (G)
        (8.0, 740.0, 1.0), (9.0, 880.0, 0.6), (9.67, 987.8, 0.8),
        # Bar 5 (Em)
        (10.67, 1174.7, 1.4), (12.33, 987.8, 0.8),
        # Bar 6 (A - resolves smoothly towards D)
        (13.33, 880.0, 1.0), (14.5, 740.0, 0.8), (15.33, 587.3, 0.6),
    ]
    
    for t_start, freq, dur in melody_notes:
        idx_m = int(t_start * SAMPLE_RATE)
        span_m = int(dur * SAMPLE_RATE)
        if idx_m + span_m > total_samples:
            span_m = total_samples - idx_m
        t_m = np.linspace(0, dur, span_m)
        # Vibrato & breath
        vib = 1.0 + 0.018 * np.sin(2 * np.pi * 5.2 * t_m)
        flute = np.sin(2 * np.pi * freq * vib * t_m) + 0.2 * np.sin(2 * np.pi * freq * 2 * vib * t_m)
        breath = butter_filter(white_noise(span_m), [1500, 5000], btype='bandpass') * 0.12
        env_m = adsr_env(span_m, 0.08, 0.15, 0.7, 0.15)
        flute_sig = (flute + breath) * env_m
        
        # Center-left flute
        left[idx_m:idx_m+span_m] += flute_sig * 0.32
        right[idx_m:idx_m+span_m] += flute_sig * 0.24

    # 4. Soft Ambient Village Pad
    t_tot = np.linspace(0, total_dur, total_samples)
    pad = (np.sin(2 * np.pi * 293.7 * t_tot) + 0.6 * np.sin(2 * np.pi * 440.0 * t_tot)) * (0.8 + 0.2 * np.sin(2 * np.pi * 0.25 * t_tot))
    pad = butter_filter(pad, 800, btype='low') * 0.1
    left += pad
    right += pad

    # Reverb
    left_rev, right_rev = stereo_reverb(left, right, delay_ms=45, feedback=0.45, wet=0.25)
    
    # CIRCULAR OVERLAP FOR 100% SEAMLESS LOOP
    # Wrap tail back into the beginning
    tail_len = total_samples - loop_samples
    left_loop = left_rev[:loop_samples].copy()
    right_loop = right_rev[:loop_samples].copy()
    left_loop[:tail_len] += left_rev[loop_samples:]
    right_loop[:tail_len] += right_rev[loop_samples:]
    
    stereo_out = np.stack([left_loop, right_loop])
    return stereo_out

def synthesize_music_kuzey_ormani():
    """
    Mysterious ancient northern forest ambient pad with wooden percussion.
    Duration: 16.0s (seamless loop via circular overlap).
    Tempo: 72 BPM. Key: E Dorian / A Minor Modal.
    """
    loop_dur = 16.0
    tail_dur = 3.0
    total_dur = loop_dur + tail_dur
    total_samples = int(total_dur * SAMPLE_RATE)
    loop_samples = int(loop_dur * SAMPLE_RATE)
    
    left = np.zeros(total_samples)
    right = np.zeros(total_samples)
    
    beat_sec = 60.0 / 72.0 # 0.8333s
    
    # 1. Atmospheric Mossy Pad (E Dorian open 5ths & 9ths: E2, B2, F#3, G3, D4)
    t_tot = np.linspace(0, total_dur, total_samples)
    pad_e = np.sin(2 * np.pi * 82.4 * t_tot) # E2
    pad_b = np.sin(2 * np.pi * 123.5 * t_tot) # B2
    pad_fs = np.sin(2 * np.pi * 185.0 * t_tot) # F#3
    pad_d = np.sin(2 * np.pi * 293.7 * t_tot) # D4
    
    # Slow LFO filter sweep
    lfo_pad = 0.5 + 0.5 * np.sin(2 * np.pi * 0.125 * t_tot) # 8 second cycle
    raw_pad = (pad_e * 0.4 + pad_b * 0.35 + pad_fs * 0.25 + pad_d * 0.2)
    flt_pad = butter_filter(raw_pad, 650, btype='low') * (0.7 + 0.3 * lfo_pad) * 0.35
    
    left += flt_pad * 0.8
    right += flt_pad * 0.8
    
    # 2. Wooden Percussion (Slit drum & hollow log taps)
    wood_pattern = [
        (0.0, 180), (0.83, 240), (1.67, 180), (2.08, 310),
        (3.33, 195), (4.17, 240), (5.0, 180), (5.83, 330),
        (6.67, 180), (7.5, 240), (8.33, 195), (9.17, 310),
        (10.0, 180), (11.25, 260), (12.5, 180), (13.33, 240),
        (14.17, 330), (15.0, 195),
    ]
    for t_hit, freq in wood_pattern:
        idx_h = int(t_hit * SAMPLE_RATE)
        span_h = int(0.12 * SAMPLE_RATE)
        if idx_h + span_h > total_samples:
            span_h = total_samples - idx_h
        t_h = np.linspace(0, 0.12, span_h)
        # Hollow wooden click + sine decay
        wood_hit = np.sin(2 * np.pi * freq * t_h) * np.exp(-32 * t_h)
        wood_hit += butter_filter(white_noise(span_h), [freq*0.8, freq*2.2], btype='bandpass') * np.exp(-45 * t_h) * 0.4
        
        # Panning
        pan = 0.4 + 0.2 * np.sin(freq)
        left[idx_h:idx_h+span_h] += wood_hit * (1.0 - pan) * 0.35
        right[idx_h:idx_h+span_h] += wood_hit * pan * 0.35

    # 3. Mystical Forest Chime Echoes (E minor pentatonic: E5, G5, A5, B5, D6)
    chime_melody = [
        (1.2, 659.3), (2.8, 783.9), (4.5, 987.8), (6.0, 1174.7),
        (8.5, 880.0), (10.2, 783.9), (12.0, 659.3), (13.8, 987.8),
    ]
    for t_ch, freq in chime_melody:
        idx_c = int(t_ch * SAMPLE_RATE)
        span_c = int(1.2 * SAMPLE_RATE)
        if idx_c + span_c > total_samples:
            span_c = total_samples - idx_c
        t_c = np.linspace(0, 1.2, span_c)
        chime_sig = (np.sin(2 * np.pi * freq * t_c) + 0.25 * np.sin(2 * np.pi * freq * 2.75 * t_c)) * np.exp(-5.5 * t_c)
        pan = 0.3 if freq > 800 else 0.7
        left[idx_c:idx_c+span_c] += chime_sig * (1.0 - pan) * 0.25
        right[idx_c:idx_c+span_c] += chime_sig * pan * 0.25

    # 4. Wind Canopy Rustle
    wind = butter_filter(pink_noise(total_samples), [200, 1200], btype='bandpass') * (0.08 + 0.04 * np.sin(2 * np.pi * 0.2 * t_tot))
    left += wind * 0.5
    right += wind * 0.5

    # Reverb
    left_rev, right_rev = stereo_reverb(left, right, delay_ms=55, feedback=0.5, wet=0.3)
    
    # Circular overlap
    tail_len = total_samples - loop_samples
    left_loop = left_rev[:loop_samples].copy()
    right_loop = right_rev[:loop_samples].copy()
    left_loop[:tail_len] += left_rev[loop_samples:]
    right_loop[:tail_len] += right_rev[loop_samples:]
    
    stereo_out = np.stack([left_loop, right_loop])
    return stereo_out

def synthesize_music_boss_battle():
    """
    Intense, driving battle percussion, orchestral hits, rapid arpeggio in D Minor.
    Duration: 16.0s (seamless loop via circular overlap).
    Tempo: 135 BPM. 1 beat = 0.4444s. 4 beats/bar = 1.7778s. 9 bars = 16.0s.
    """
    loop_dur = 16.0
    tail_dur = 2.5
    total_dur = loop_dur + tail_dur
    total_samples = int(total_dur * SAMPLE_RATE)
    loop_samples = int(loop_dur * SAMPLE_RATE)
    
    left = np.zeros(total_samples)
    right = np.zeros(total_samples)
    
    beat_sec = 60.0 / 135.0 # 0.4444s
    step_16th = beat_sec / 4.0 # 0.1111s
    
    # 1. Driving Battle Percussion (Taiko Kick & Snare / Anvil Drive)
    # Total 36 beats in 16 seconds
    n_beats = int(loop_dur / beat_sec)
    for b in range(n_beats + 4):
        t_b = b * beat_sec
        idx_b = int(t_b * SAMPLE_RATE)
        if idx_b >= total_samples:
            break
            
        # Heavy Taiko Kick on 1 and 3 (and syncopated variations)
        if b % 2 == 0 or (b % 4 == 3 and b % 8 == 7):
            span_k = int(0.25 * SAMPLE_RATE)
            if idx_b + span_k <= total_samples:
                t_k = np.linspace(0, 0.25, span_k)
                kick = np.sin(2 * np.pi * np.geomspace(120, 38, span_k) * t_k) * exp_decay_env(span_k, 14.0)
                left[idx_b:idx_b+span_k] += kick * 0.45
                right[idx_b:idx_b+span_k] += kick * 0.45
                
        # Snare / Anvil strike on beats 2 and 4
        if b % 2 == 1:
            span_s = int(0.2 * SAMPLE_RATE)
            if idx_b + span_s <= total_samples:
                t_s = np.linspace(0, 0.2, span_s)
                snare = butter_filter(white_noise(span_s), [800, 4500], btype='bandpass') * exp_decay_env(span_s, 22.0)
                anvil = np.sin(2 * np.pi * 1850 * t_s) * exp_decay_env(span_s, 25.0) * 0.3
                hit = snare * 0.4 + anvil
                left[idx_b:idx_b+span_s] += hit * 0.35
                right[idx_b:idx_b+span_s] += hit * 0.35

    # 2. Driving 16th-note Synth Bass Arpeggio in D Minor
    # Notes: D2 (73.4), F2 (87.3), A2 (110.0), D3 (146.8)
    bass_notes = [73.4, 73.4, 87.3, 73.4, 110.0, 73.4, 87.3, 110.0]
    total_16ths = int(loop_dur / step_16th)
    for s in range(total_16ths):
        t_s = s * step_16th
        idx_s = int(t_s * SAMPLE_RATE)
        span_s = int(step_16th * 0.9 * SAMPLE_RATE)
        if idx_s + span_s > total_samples:
            span_s = total_samples - idx_s
        freq = bass_notes[s % len(bass_notes)]
        t_bass = np.linspace(0, span_s / SAMPLE_RATE, span_s)
        # Punchy saw-bass
        phase = 2 * np.pi * freq * t_bass
        saw_b = 2.0 * (phase / (2 * np.pi) - np.floor(phase / (2 * np.pi) + 0.5))
        flt_saw = butter_filter(saw_b, 650, btype='low') * adsr_env(span_s, 0.01, 0.04, 0.6, 0.02)
        left[idx_s:idx_s+span_s] += flt_saw * 0.35
        right[idx_s:idx_s+span_s] += flt_saw * 0.35

    # 3. Orchestral Hits & Gothic Minor Chords (Dmin - Bb - Gmin - A7)
    # Chord changes every 2 bars (3.55s)
    chords = [
        [293.7, 349.2, 440.0], # Dm
        [233.1, 293.7, 349.2], # Bb
        [196.0, 233.1, 293.7], # Gm
        [220.0, 277.2, 329.6], # A
    ]
    chord_interval = 3.555 # 2 bars
    for c_idx, chord_freqs in enumerate(chords):
        t_c = c_idx * chord_interval
        idx_c = int(t_c * SAMPLE_RATE)
        span_c = int(chord_interval * 0.85 * SAMPLE_RATE)
        if idx_c + span_c > total_samples:
            span_c = total_samples - idx_c
        t_chord = np.linspace(0, span_c / SAMPLE_RATE, span_c)
        chord_sig = np.zeros(span_c)
        for cf in chord_freqs:
            chord_sig += np.sin(2 * np.pi * cf * t_chord) + 0.3 * np.sin(2 * np.pi * cf * 2 * t_chord)
        chord_sig *= adsr_env(span_c, 0.04, 0.3, 0.5, 0.3)
        left[idx_c:idx_c+span_c] += chord_sig * 0.22
        right[idx_c:idx_c+span_c] += chord_sig * 0.22

    # 4. High-Tension Lead Arpeggio
    # Fast 8th-note lead cutting through: D5, F5, E5, D5, A5, G5, F5, E5
    lead_notes = [587.3, 698.5, 659.3, 587.3, 880.0, 783.9, 698.5, 659.3]
    step_8th = beat_sec / 2.0
    total_8ths = int(loop_dur / step_8th)
    for e in range(total_8ths):
        t_e = e * step_8th
        idx_e = int(t_e * SAMPLE_RATE)
        span_e = int(step_8th * 0.85 * SAMPLE_RATE)
        if idx_e + span_e > total_samples:
            span_e = total_samples - idx_e
        freq = lead_notes[e % len(lead_notes)]
        t_lead = np.linspace(0, span_e / SAMPLE_RATE, span_e)
        lead_sig = np.sin(2 * np.pi * freq * t_lead) * adsr_env(span_e, 0.02, 0.06, 0.6, 0.03)
        pan = 0.35 if e % 2 == 0 else 0.65
        left[idx_e:idx_e+span_e] += lead_sig * (1.0 - pan) * 0.22
        right[idx_e:idx_e+span_e] += lead_sig * pan * 0.22

    # Reverb
    left_rev, right_rev = stereo_reverb(left, right, delay_ms=40, feedback=0.4, wet=0.22)
    
    # Circular overlap for seamless loop
    tail_len = total_samples - loop_samples
    left_loop = left_rev[:loop_samples].copy()
    right_loop = right_rev[:loop_samples].copy()
    left_loop[:tail_len] += left_rev[loop_samples:]
    right_loop[:tail_len] += right_rev[loop_samples:]
    
    stereo_out = np.stack([left_loop, right_loop])
    return stereo_out

# ==============================================================================
# 9. MASTER BATCH GENERATOR
# ==============================================================================

SFX_REGISTRY = {
    # A) Combat & Weapon SFX
    "sfx_sword_slash_light.wav": syn_sword_slash_light,
    "sfx_sword_slash_heavy.wav": syn_sword_slash_heavy,
    "sfx_sword_slash_crit.wav": syn_sword_slash_crit,
    "sfx_bow_draw.wav": syn_bow_draw,
    "sfx_arrow_shoot.wav": syn_arrow_shoot,
    "sfx_arrow_impact.wav": syn_arrow_impact,
    "sfx_shield_block.wav": syn_shield_block,
    
    # B) Magic & Elemental SFX
    "sfx_fire_cast.wav": syn_fire_cast,
    "sfx_fire_ring_roar.wav": syn_fire_ring_roar,
    "sfx_water_splash.wav": syn_water_splash,
    "sfx_ice_freeze.wav": syn_ice_freeze,
    "sfx_frost_shatter.wav": syn_frost_shatter,
    "sfx_steam_hiss.wav": syn_steam_hiss,
    "sfx_magic_orb_shoot.wav": syn_magic_orb_shoot,
    
    # C) Impacts, Hit-Stops & Monsters
    "sfx_hit_punchy.wav": syn_hit_punchy,
    "sfx_hit_stomp_aoe.wav": syn_hit_stomp_aoe,
    "sfx_imp_groan.wav": syn_imp_groan,
    "sfx_boss_roar.wav": syn_boss_roar,
    "sfx_monster_death_dissolve.wav": syn_monster_death_dissolve,
    
    # D) Loot, Economy & Progression
    "sfx_gold_pickup.wav": syn_gold_pickup,
    "sfx_loot_drop_common.wav": syn_loot_drop_common,
    "sfx_loot_drop_rare.wav": syn_loot_drop_rare,
    "sfx_loot_drop_unique.wav": syn_loot_drop_unique,
    "sfx_level_up.wav": syn_level_up,
    "sfx_craft_hammer.wav": syn_craft_hammer,
    "sfx_upgrade_success.wav": syn_upgrade_success,
    "sfx_upgrade_fail.wav": syn_upgrade_fail,
    "sfx_potion_drink.wav": syn_potion_drink,
    
    # E) Pets
    "sfx_pet_turtle_taunt.wav": syn_pet_turtle_taunt,
    "sfx_pet_raven_caw.wav": syn_pet_raven_caw,
    "sfx_pet_fox_bark.wav": syn_pet_fox_bark,
    
    # F) UI
    "sfx_ui_click.wav": syn_ui_click,
    "sfx_ui_hover.wav": syn_ui_hover,
    "sfx_ui_bag_open.wav": syn_ui_bag_open,
    "sfx_ui_quest_accept.wav": syn_ui_quest_accept,
}

MUSIC_REGISTRY = {
    "music_village_hub_theme.wav": synthesize_music_village_hub,
    "music_kuzey_ormani_theme.wav": synthesize_music_kuzey_ormani,
    "music_boss_battle_theme.wav": synthesize_music_boss_battle,
}

def main():
    print("=" * 70)
    print("Aestra: The Last Wish - Audio & SFX Batch Synthesizer")
    print("=" * 70)
    
    base_dir = Path(__file__).resolve().parent.parent / "projects" / "nos" / "assets" / "audio"
    sfx_dir = base_dir / "sfx"
    music_dir = base_dir / "music"
    
    sfx_dir.mkdir(parents=True, exist_ok=True)
    music_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"\n[1/2] Synthesizing {len(SFX_REGISTRY)} Sound Effects...")
    sfx_count = 0
    for filename, syn_func in SFX_REGISTRY.items():
        wav_path = sfx_dir / filename
        print(f"  -> Synthesizing: {filename}...", end="", flush=True)
        samples = syn_func()
        save_wav_file(wav_path, samples, channels=1)
        generate_godot_import(wav_path, is_loop=False)
        print(" [OK]")
        sfx_count += 1
        
    print(f"\n[2/2] Synthesizing {len(MUSIC_REGISTRY)} Seamless Music Loops...")
    music_count = 0
    for filename, syn_func in MUSIC_REGISTRY.items():
        wav_path = music_dir / filename
        print(f"  -> Synthesizing stem: {filename}...", end="", flush=True)
        stereo_samples = syn_func()
        save_wav_file(wav_path, stereo_samples, channels=2)
        generate_godot_import(wav_path, is_loop=True)
        print(" [OK]")
        music_count += 1
        
    print("\n" + "=" * 70)
    print(f"Batch Complete: Generated {sfx_count} SFX and {music_count} Music Loops + .import files!")
    print(f"SFX Directory: {sfx_dir}")
    print(f"Music Directory: {music_dir}")
    print("=" * 70)

if __name__ == "__main__":
    main()
